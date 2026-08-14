from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.database import get_db
from app.models.investition import Investition
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.models.user import User
from app.models.veredelungsschritt import Veredelungsschritt
from app.schemas.spritzguss_kalkulation import (
    SpritzgussCalcRequest,
    SpritzgussCalcResponse,
    SpritzgussErgebnisSchema,
    SpritzgussKalkulationCreate,
    SpritzgussKalkulationListItem,
    SpritzgussKalkulationRead,
    SpritzgussKalkulationUpdate,
)
from app.schemas.spritzguss_veredelung import (
    VeredelungReihenfolgeUpdate,
    VeredelungZuordnungInput,
    VeredelungZuordnungRead,
    VeredelungZuordnungUpdate,
)
from app.services.spritzguss_gesamt_kalkulation import (
    GesamtValidationError,
    VeredelungSchrittEingabe,
    berechne_gesamt,
)
from app.services.spritzguss_kalkulation import (
    SpritzgussInput,
    SpritzgussValidationError,
    berechne_spritzguss,
)
from app.services.veredelung_kalkulation import berechne_veredelung
from app.services.veredelung_kalkulation import VeredelungInput as VeredelungCalcInput

router = APIRouter(prefix="/spritzguss", tags=["Spritzguss-Kalkulation"])


def _normalize_veredelung_zuordnungen(
    zuordnungen: list[VeredelungZuordnungInput | dict[str, Any]] | None,
) -> list[VeredelungZuordnungInput]:
    """Wandelt Dict- oder Pydantic-Eingaben in Validierte Zuordnungen um."""
    if not zuordnungen:
        return []

    normalized: list[VeredelungZuordnungInput] = []
    seen_ids: set[int] = set()

    for index, item in enumerate(zuordnungen, start=1):
        if isinstance(item, VeredelungZuordnungInput):
            zuordnung = item
        elif isinstance(item, dict):
            raw_id = item.get("veredelungsschritt_id")
            if raw_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Veredelungszuordnung #{index}: veredelungsschritt_id fehlt",
                )
            reihenfolge = item.get("reihenfolge", item.get("sequence"))
            if reihenfolge is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Veredelungszuordnung #{index}: reihenfolge fehlt",
                )
            payload = {
                "veredelungsschritt_id": raw_id,
                "reihenfolge": reihenfolge,
                "aktiv": item.get("aktiv", True),
                "mengenfaktor": item.get("mengenfaktor", item.get("quantity_factor", 1.0)),
            }
            try:
                zuordnung = VeredelungZuordnungInput.model_validate(payload)
            except ValidationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Veredelungszuordnung #{index}: {exc.errors()[0]['msg']}",
                ) from exc
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Veredelungszuordnung #{index}: ungültiges Format",
            )

        if zuordnung.veredelungsschritt_id in seen_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Veredelungsschritt {zuordnung.veredelungsschritt_id} "
                    "ist doppelt zugeordnet"
                ),
            )
        seen_ids.add(zuordnung.veredelungsschritt_id)
        normalized.append(zuordnung)

    return normalized


def _to_calc_input_from_request(body: SpritzgussCalcRequest) -> SpritzgussInput:
    data = body.model_dump(exclude={"veredelung_zuordnungen"})
    return SpritzgussInput(**data)


def _to_calc_input_from_model(obj: SpritzgussKalkulation) -> SpritzgussInput:
    art = getattr(obj, "werkzeug_abrechnungsart", None) or "amortisation"
    volumen = obj.amortisationsvolumen
    if art == "amortisation" and volumen is not None:
        volumen = int(volumen)
    elif art != "amortisation":
        volumen = None

    return SpritzgussInput(
        teilegewicht_netto_g=obj.teilegewicht_netto_g,
        materialpreis_pro_kg=obj.materialpreis_pro_kg,
        ausschussquote_pct=obj.ausschussquote_pct,
        mgk_pct=obj.mgk_pct,
        zykluszeit_s=obj.zykluszeit_s,
        maschinenstundensatz=obj.maschinenstundensatz,
        kavitaeten=obj.kavitaeten,
        lohnstundensatz=obj.lohnstundensatz,
        fgk_pct=obj.fgk_pct,
        werkzeugkosten_eur=obj.werkzeugkosten_eur,
        werkzeug_abrechnungsart=art,  # type: ignore[arg-type]
        amortisationsvolumen=volumen,
        vvgk_pct=obj.vvgk_pct,
        gewinn_pct=obj.gewinn_pct,
        skonto_pct=obj.skonto_pct,
    )


def _live_kosten_fuer_veredelungsschritt(schritt: Veredelungsschritt) -> float:
    kosten = berechne_veredelung(
        VeredelungCalcInput(
            taktzeit_s=schritt.taktzeit_s,
            anzahl_mitarbeiter=schritt.anzahl_mitarbeiter,
            lohnstundensatz=schritt.lohnstundensatz,
            maschinenstundensatz=schritt.maschinenstundensatz,
            verbrauchskosten_je_stueck=schritt.verbrauchskosten_je_stueck,
            ausschussquote_pct=schritt.ausschussquote_pct,
            fgk_pct=schritt.fgk_pct,
            reihenfolge=schritt.reihenfolge,
        )
    )
    return kosten.kosten_inkl_ausschuss


def _resolve_veredelung_eingaben(
    db: Session,
    zuordnungen: list[VeredelungZuordnungInput | dict[str, Any]],
    *,
    use_snapshots: bool,
    kalkulation_id: int | None = None,
) -> list[VeredelungSchrittEingabe]:
    zuordnungen = _normalize_veredelung_zuordnungen(zuordnungen)
    if not zuordnungen:
        return []

    snapshot_map: dict[int, SpritzgussVeredelungZuordnung] = {}
    if use_snapshots and kalkulation_id is not None:
        rows = db.scalars(
            select(SpritzgussVeredelungZuordnung).where(
                SpritzgussVeredelungZuordnung.kalkulation_id == kalkulation_id
            )
        ).all()
        snapshot_map = {row.veredelungsschritt_id: row for row in rows}

    eingaben: list[VeredelungSchrittEingabe] = []
    for zuordnung in zuordnungen:
        schritt = db.get(Veredelungsschritt, zuordnung.veredelungsschritt_id)
        if not schritt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Veredelungsschritt {zuordnung.veredelungsschritt_id} nicht gefunden",
            )
        if not use_snapshots and not schritt.aktiv:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Veredelungsschritt '{schritt.bezeichnung}' ist inaktiv",
            )

        snapshot = snapshot_map.get(zuordnung.veredelungsschritt_id)
        if use_snapshots and snapshot is not None:
            kosten = snapshot.snapshot_kosten_inkl_ausschuss
            bezeichnung = snapshot.snapshot_bezeichnung
            art = snapshot.snapshot_veredelungsart
        else:
            kosten = _live_kosten_fuer_veredelungsschritt(schritt)
            bezeichnung = schritt.bezeichnung
            art = schritt.veredelungsart

        eingaben.append(
            VeredelungSchrittEingabe(
                veredelungsschritt_id=zuordnung.veredelungsschritt_id,
                bezeichnung=bezeichnung,
                veredelungsart=art,
                reihenfolge=zuordnung.reihenfolge,
                aktiv=zuordnung.aktiv,
                mengenfaktor=zuordnung.mengenfaktor,
                kosten_inkl_ausschuss=kosten,
            )
        )
    return eingaben


def _zuordnung_read(
    row: SpritzgussVeredelungZuordnung,
    *,
    kosten_gesamt: float | None = None,
) -> VeredelungZuordnungRead:
    if kosten_gesamt is None:
        kosten_gesamt = (
            row.snapshot_kosten_inkl_ausschuss * row.mengenfaktor if row.aktiv else 0.0
        )
    return VeredelungZuordnungRead(
        id=row.id,
        kalkulation_id=row.kalkulation_id,
        veredelungsschritt_id=row.veredelungsschritt_id,
        reihenfolge=row.reihenfolge,
        aktiv=row.aktiv,
        mengenfaktor=row.mengenfaktor,
        snapshot_bezeichnung=row.snapshot_bezeichnung,
        snapshot_veredelungsart=row.snapshot_veredelungsart,
        snapshot_kosten_inkl_ausschuss=row.snapshot_kosten_inkl_ausschuss,
        kosten_gesamt=kosten_gesamt,
    )


def _load_zuordnungen(db: Session, kalkulation_id: int) -> list[SpritzgussVeredelungZuordnung]:
    return list(
        db.scalars(
            select(SpritzgussVeredelungZuordnung)
            .where(SpritzgussVeredelungZuordnung.kalkulation_id == kalkulation_id)
            .order_by(
                SpritzgussVeredelungZuordnung.reihenfolge.asc(),
                SpritzgussVeredelungZuordnung.id.asc(),
            )
        ).all()
    )


def _sync_veredelung_zuordnungen(
    db: Session,
    obj: SpritzgussKalkulation,
    zuordnungen: list[VeredelungZuordnungInput | dict[str, Any]],
) -> list[SpritzgussVeredelungZuordnung]:
    """Ersetzt Zuordnungen und speichert Kosten-Snapshots."""
    zuordnungen = _normalize_veredelung_zuordnungen(zuordnungen)
    for existing in _load_zuordnungen(db, obj.id):
        db.delete(existing)
    db.flush()

    created: list[SpritzgussVeredelungZuordnung] = []
    for zuordnung in zuordnungen:
        schritt = db.get(Veredelungsschritt, zuordnung.veredelungsschritt_id)
        if not schritt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Veredelungsschritt {zuordnung.veredelungsschritt_id} nicht gefunden",
            )
        kosten = _live_kosten_fuer_veredelungsschritt(schritt)
        row = SpritzgussVeredelungZuordnung(
            kalkulation_id=obj.id,
            veredelungsschritt_id=zuordnung.veredelungsschritt_id,
            reihenfolge=zuordnung.reihenfolge,
            aktiv=zuordnung.aktiv,
            mengenfaktor=zuordnung.mengenfaktor,
            snapshot_bezeichnung=schritt.bezeichnung,
            snapshot_veredelungsart=schritt.veredelungsart,
            snapshot_kosten_inkl_ausschuss=kosten,
        )
        db.add(row)
        created.append(row)
    db.flush()
    return created


def _build_calc_response(
    db: Session,
    calc_input: SpritzgussInput,
    zuordnungen: list[VeredelungZuordnungInput | dict[str, Any]],
    *,
    use_snapshots: bool = False,
    kalkulation_id: int | None = None,
    saved_rows: list[SpritzgussVeredelungZuordnung] | None = None,
) -> SpritzgussCalcResponse:
    zuordnungen = _normalize_veredelung_zuordnungen(zuordnungen)
    try:
        spritzguss = berechne_spritzguss(calc_input)
    except SpritzgussValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    spritzguss_dict = spritzguss.to_dict()
    bloecke = spritzguss.as_blocks()

    try:
        veredelung_eingaben = _resolve_veredelung_eingaben(
            db,
            zuordnungen,
            use_snapshots=use_snapshots,
            kalkulation_id=kalkulation_id,
        )
        gesamt = berechne_gesamt(
            spritzguss_dict,
            veredelung_eingaben,
            vvgk_pct=calc_input.vvgk_pct,
            gewinn_pct=calc_input.gewinn_pct,
            skonto_pct=calc_input.skonto_pct,
        )
    except GesamtValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    ergebnis_dict = {
        **spritzguss_dict,
        **gesamt.to_dict(),
        "verkaufspreis": spritzguss_dict["verkaufspreis"],
    }

    bloecke["gemeinkosten"] = {
        "herstellkosten": gesamt.gesamte_herstellkosten,
        "vvgk": gesamt.vvgk,
        "selbstkosten": gesamt.selbstkosten,
        "gewinn": gesamt.gewinn,
    }
    bloecke["verkaufspreis"] = {
        "nettoverkaufspreis": gesamt.nettoverkaufspreis,
        "skonto": gesamt.skonto,
        "verkaufspreis": gesamt.endpreis_je_stueck,
    }
    bloecke["zusammenfassung"] = gesamt.as_ergebnisuebersicht()
    if gesamt.veredelung_gesamt > 0 or gesamt.veredelung_schritte:
        bloecke["veredelung"] = gesamt.as_veredelung_block()

    zuordnung_reads: list[VeredelungZuordnungRead] = []
    if saved_rows is not None:
        kosten_map = {
            s.veredelungsschritt_id: s.kosten_gesamt for s in gesamt.veredelung_schritte
        }
        zuordnung_reads = [
            _zuordnung_read(row, kosten_gesamt=kosten_map.get(row.veredelungsschritt_id, 0))
            for row in saved_rows
        ]
    elif zuordnungen:
        kosten_map = {
            s.veredelungsschritt_id: s.kosten_gesamt for s in gesamt.veredelung_schritte
        }
        for z in sorted(zuordnungen, key=lambda x: x.reihenfolge):
            schritt = next(s for s in gesamt.veredelung_schritte if s.veredelungsschritt_id == z.veredelungsschritt_id)
            zuordnung_reads.append(
                VeredelungZuordnungRead(
                    id=0,
                    kalkulation_id=kalkulation_id or 0,
                    veredelungsschritt_id=z.veredelungsschritt_id,
                    reihenfolge=z.reihenfolge,
                    aktiv=z.aktiv,
                    mengenfaktor=z.mengenfaktor,
                    snapshot_bezeichnung=schritt.bezeichnung,
                    snapshot_veredelungsart=schritt.veredelungsart,
                    snapshot_kosten_inkl_ausschuss=schritt.kosten_inkl_ausschuss,
                    kosten_gesamt=kosten_map.get(z.veredelungsschritt_id, 0),
                )
            )

    return SpritzgussCalcResponse(
        ergebnis=SpritzgussErgebnisSchema(**ergebnis_dict),
        bloecke=bloecke,
        veredelung_zuordnungen=zuordnung_reads,
    )


def _apply_calculation(
    db: Session,
    obj: SpritzgussKalkulation,
    zuordnungen: list[VeredelungZuordnungInput] | None = None,
    *,
    use_snapshots: bool = False,
) -> SpritzgussCalcResponse:
    if zuordnungen is None:
        rows = _load_zuordnungen(db, obj.id)
        zuordnungen = [
            VeredelungZuordnungInput(
                veredelungsschritt_id=row.veredelungsschritt_id,
                reihenfolge=row.reihenfolge,
                aktiv=row.aktiv,
                mengenfaktor=row.mengenfaktor,
            )
            for row in rows
        ]
        use_snapshots = True

    response = _build_calc_response(
        db,
        _to_calc_input_from_model(obj),
        zuordnungen,
        use_snapshots=use_snapshots,
        kalkulation_id=obj.id,
        saved_rows=_load_zuordnungen(db, obj.id) if obj.id else None,
    )
    obj.ergebnis = response.ergebnis.model_dump()
    obj.ergebnis_bloecke = response.bloecke
    return response


def _kalkulation_to_read(db: Session, obj: SpritzgussKalkulation) -> SpritzgussKalkulationRead:
    rows = _load_zuordnungen(db, obj.id)
    kosten_map: dict[int, float] = {}
    if isinstance(obj.ergebnis, dict):
        for schritt in obj.ergebnis.get("veredelung_schritte", []) or []:
            if isinstance(schritt, dict):
                kosten_map[schritt.get("veredelungsschritt_id", 0)] = schritt.get(
                    "kosten_gesamt", 0
                )
    zuordnungen = [
        _zuordnung_read(row, kosten_gesamt=kosten_map.get(row.veredelungsschritt_id))
        for row in rows
    ]
    base = SpritzgussKalkulationRead.model_validate(obj)
    return base.model_copy(update={"veredelung_zuordnungen": zuordnungen})


def _run_calculation(
    db: Session,
    calc_input: SpritzgussInput,
    zuordnungen: list[VeredelungZuordnungInput],
) -> SpritzgussCalcResponse:
    return _build_calc_response(db, calc_input, zuordnungen, use_snapshots=False)


def _sync_werkzeug_investition(db: Session, obj: SpritzgussKalkulation) -> None:
    """Legt/aktualisiert/löscht die zugehörige Werkzeug-Einmalzahlung."""
    existing = db.scalars(
        select(Investition).where(
            Investition.calculation_id == obj.id,
            Investition.investment_type == "Werkzeug",
            Investition.payment_type == "Einmalzahlung",
        )
    ).first()

    art = getattr(obj, "werkzeug_abrechnungsart", "amortisation")
    if art != "einmalzahlung" or obj.werkzeugkosten_eur <= 0:
        if existing:
            db.delete(existing)
        return

    description = (
        f"Werkzeug-Einmalzahlung für {obj.teilenummer} – {obj.teilebezeichnung}"
    )
    if existing:
        existing.project_id = obj.projekt or ""
        existing.customer = obj.kunde or ""
        existing.part_name = obj.teilebezeichnung
        existing.part_number = obj.teilenummer or ""
        existing.name = f"Werkzeug {obj.teilenummer}".strip() or "Werkzeug-Einmalzahlung"
        existing.description = description
        existing.amount = obj.werkzeugkosten_eur
        existing.status = "In Planung"
        existing.included_in_unit_price = False
        existing.amortization_volume = None
        existing.cost_per_piece = None
    else:
        db.add(
            Investition(
                project_id=obj.projekt or "",
                customer=obj.kunde or "",
                calculation_id=obj.id,
                part_name=obj.teilebezeichnung,
                part_number=obj.teilenummer or "",
                name=f"Werkzeug {obj.teilenummer}".strip() or "Werkzeug-Einmalzahlung",
                description=description,
                amount=obj.werkzeugkosten_eur,
                investment_type="Werkzeug",
                payment_type="Einmalzahlung",
                status="In Planung",
                included_in_unit_price=False,
            )
        )


@router.post("/berechnen", response_model=SpritzgussCalcResponse)
def berechnen(
    body: SpritzgussCalcRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    """Berechnet eine Kalkulation ohne Speichern."""
    return _run_calculation(
        db,
        _to_calc_input_from_request(body),
        body.veredelung_zuordnungen,
    )


@router.get("", response_model=list[SpritzgussKalkulationListItem])
def list_kalkulationen(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    rows = db.scalars(
        select(SpritzgussKalkulation)
        .order_by(SpritzgussKalkulation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    ).all()
    result: list[SpritzgussKalkulationListItem] = []
    for row in rows:
        verkaufspreis = None
        if isinstance(row.ergebnis, dict):
            verkaufspreis = row.ergebnis.get("endpreis_je_stueck")
            if verkaufspreis is None:
                verkaufspreis = row.ergebnis.get("verkaufspreis")
        result.append(
            SpritzgussKalkulationListItem(
                id=row.id,
                teilebezeichnung=row.teilebezeichnung,
                teilenummer=row.teilenummer,
                kunde=row.kunde,
                projekt=row.projekt,
                jahresstueckzahl=row.jahresstueckzahl,
                verkaufspreis=verkaufspreis,
                updated_at=row.updated_at,
                aktiv=row.aktiv,
            )
        )
    return result


@router.get("/{item_id}", response_model=SpritzgussKalkulationRead)
def get_kalkulation(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = db.get(SpritzgussKalkulation, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    return _kalkulation_to_read(db, item)


@router.get("/{item_id}/veredelung", response_model=list[VeredelungZuordnungRead])
def list_veredelung_zuordnungen(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    item = db.get(SpritzgussKalkulation, item_id)
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    return _kalkulation_to_read(db, item).veredelung_zuordnungen


@router.post(
    "/{item_id}/veredelung",
    response_model=VeredelungZuordnungRead,
    status_code=status.HTTP_201_CREATED,
)
def add_veredelung_zuordnung(
    item_id: int,
    body: VeredelungZuordnungInput,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    existing = db.scalars(
        select(SpritzgussVeredelungZuordnung).where(
            SpritzgussVeredelungZuordnung.kalkulation_id == item_id,
            SpritzgussVeredelungZuordnung.veredelungsschritt_id
            == body.veredelungsschritt_id,
        )
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Veredelungsschritt ist dieser Kalkulation bereits zugeordnet",
        )
    schritt = db.get(Veredelungsschritt, body.veredelungsschritt_id)
    if not schritt:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Veredelungsschritt nicht gefunden"
        )
    kosten = _live_kosten_fuer_veredelungsschritt(schritt)
    row = SpritzgussVeredelungZuordnung(
        kalkulation_id=item_id,
        veredelungsschritt_id=body.veredelungsschritt_id,
        reihenfolge=body.reihenfolge,
        aktiv=body.aktiv,
        mengenfaktor=body.mengenfaktor,
        snapshot_bezeichnung=schritt.bezeichnung,
        snapshot_veredelungsart=schritt.veredelungsart,
        snapshot_kosten_inkl_ausschuss=kosten,
    )
    db.add(row)
    db.flush()
    _apply_calculation(db, obj, use_snapshots=True)
    db.commit()
    db.refresh(row)
    gesamt_kosten = row.snapshot_kosten_inkl_ausschuss * row.mengenfaktor if row.aktiv else 0
    return _zuordnung_read(row, kosten_gesamt=gesamt_kosten)


@router.put("/{item_id}/veredelung/reihenfolge", response_model=list[VeredelungZuordnungRead])
def update_veredelung_reihenfolge(
    item_id: int,
    body: VeredelungReihenfolgeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    rows = {row.id: row for row in _load_zuordnungen(db, item_id)}
    for item in body.zuordnungen:
        row = rows.get(item.id)
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Zuordnung {item.id} nicht gefunden",
            )
        row.reihenfolge = item.reihenfolge
    _apply_calculation(db, obj, use_snapshots=True)
    db.commit()
    return _kalkulation_to_read(db, obj).veredelung_zuordnungen


@router.put("/{item_id}/veredelung/{zuordnung_id}", response_model=VeredelungZuordnungRead)
def update_veredelung_zuordnung(
    item_id: int,
    zuordnung_id: int,
    body: VeredelungZuordnungUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    row = db.get(SpritzgussVeredelungZuordnung, zuordnung_id)
    if not row or row.kalkulation_id != item_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zuordnung nicht gefunden"
        )
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(row, field, value)
    _apply_calculation(db, obj, use_snapshots=True)
    db.commit()
    db.refresh(row)
    return _zuordnung_read(row)


@router.delete("/{item_id}/veredelung/{zuordnung_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_veredelung_zuordnung(
    item_id: int,
    zuordnung_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    row = db.get(SpritzgussVeredelungZuordnung, zuordnung_id)
    if not row or row.kalkulation_id != item_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Zuordnung nicht gefunden"
        )
    db.delete(row)
    _apply_calculation(db, obj, use_snapshots=True)
    db.commit()


@router.post("", response_model=SpritzgussKalkulationRead, status_code=status.HTTP_201_CREATED)
def create_kalkulation(
    body: SpritzgussKalkulationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    zuordnungen = body.veredelung_zuordnungen
    payload = body.model_dump(exclude={"veredelung_zuordnungen"})
    if payload.get("werkzeug_abrechnungsart") == "einmalzahlung":
        payload["amortisationsvolumen"] = None
    obj = SpritzgussKalkulation(**payload)
    db.add(obj)
    db.flush()
    _sync_veredelung_zuordnungen(db, obj, zuordnungen)
    _apply_calculation(db, obj, zuordnungen, use_snapshots=True)
    db.commit()
    db.refresh(obj)
    # Werkzeug-Investitionen werden separat im Modul Investitionen / Business Case gepflegt.
    # _sync_werkzeug_investition(db, obj)
    db.commit()
    db.refresh(obj)
    return _kalkulation_to_read(db, obj)


@router.put("/{item_id}", response_model=SpritzgussKalkulationRead)
def update_kalkulation(
    item_id: int,
    body: SpritzgussKalkulationUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )

    updates = body.model_dump(exclude_unset=True)
    zuordnungen = updates.pop("veredelung_zuordnungen", None)
    for field, value in updates.items():
        setattr(obj, field, value)

    art = getattr(obj, "werkzeug_abrechnungsart", "amortisation")
    if art == "einmalzahlung":
        obj.amortisationsvolumen = None
    elif obj.amortisationsvolumen is not None:
        obj.amortisationsvolumen = int(obj.amortisationsvolumen)

    if zuordnungen is not None:
        zuordnungen = _normalize_veredelung_zuordnungen(zuordnungen)
        _sync_veredelung_zuordnungen(db, obj, zuordnungen)

    _apply_calculation(
        db,
        obj,
        zuordnungen if zuordnungen is not None else None,
        use_snapshots=True,
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    # Werkzeug-Investitionen werden separat im Modul Investitionen / Business Case gepflegt.
    # _sync_werkzeug_investition(db, obj)
    db.commit()
    db.refresh(obj)
    return _kalkulation_to_read(db, obj)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_kalkulation(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )
    for inv in db.scalars(
        select(Investition).where(Investition.calculation_id == item_id)
    ).all():
        db.delete(inv)
    db.delete(obj)
    db.commit()

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.database import get_db
from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import BaugruppeSpritzgussZuordnung
from app.models.investition import Investition
from app.models.maschine import Maschine
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.models.user import User
from app.models.veredelungsschritt import Veredelungsschritt
from app.models.werk import Werk
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
from app.services.central_markup_rates import (
    CentralMarkupRatesError,
    load_central_markup_rates,
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
from app.services.spritzguss_hierarchy import resolve_hierarchy_for_spritzguss
from app.services.veredelung_kalkulation import berechne_veredelung
from app.services.veredelung_kalkulation import VeredelungInput as VeredelungCalcInput

router = APIRouter(prefix="/spritzguss", tags=["Spritzguss-Kalkulation"])


def _apply_central_rates(
    db: Session, calc_input: SpritzgussInput, *, werk_id: int | None = None
) -> SpritzgussInput:
    """Überschreibt Zuschlagssätze mit zentral gepflegten Stammdatenwerten."""
    try:
        rates = load_central_markup_rates(db, werk_id=werk_id)
        mgk_pct = rates.mgk_pct_for_nominierung(
            calc_input.material_nominierung,
            kontext="Spritzguss-Materialeinsatz",
        )
    except CentralMarkupRatesError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    return SpritzgussInput(
        teilegewicht_netto_g=calc_input.teilegewicht_netto_g,
        schussgewicht_g=calc_input.schussgewicht_g,
        materialpreis_pro_kg=calc_input.materialpreis_pro_kg,
        ausschussquote_pct=calc_input.ausschussquote_pct,
        mgk_pct=mgk_pct,
        material_nominierung=calc_input.material_nominierung,
        zykluszeit_s=calc_input.zykluszeit_s,
        maschinenstundensatz=calc_input.maschinenstundensatz,
        kavitaeten=calc_input.kavitaeten,
        lohnstundensatz=calc_input.lohnstundensatz,
        fgk_pct=rates.fgk_pct,
        werkzeugkosten_eur=calc_input.werkzeugkosten_eur,
        werkzeug_abrechnungsart=calc_input.werkzeug_abrechnungsart,
        amortisationsvolumen=calc_input.amortisationsvolumen,
        vvgk_pct=rates.vvgk_pct,
        gewinn_pct=rates.gewinn_pct,
        skonto_pct=rates.skonto_pct,
        setup_zeit_min=calc_input.setup_zeit_min,
        setup_maschinenstundensatz=calc_input.setup_maschinenstundensatz,
        setup_lohnstundensatz=calc_input.setup_lohnstundensatz,
        setup_mitarbeiter=calc_input.setup_mitarbeiter,
        losgroesse=calc_input.losgroesse,
        setup_aktiv=calc_input.setup_aktiv,
    )


def _apply_hierarchy_payload(db: Session, payload: dict) -> dict:
    """Setzt kunde/projekt aus zentraler Hierarchie, wenn IDs gesetzt sind."""
    cid = payload.get("customer_id")
    pid = payload.get("program_id")
    prid = payload.get("project_id")
    year = payload.get("calculation_year")
    if cid is None and pid is None and prid is None:
        return payload
    if None in (cid, pid, prid):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Kunde, Programm und Projekt müssen gemeinsam angegeben werden.",
        )
    resolved = resolve_hierarchy_for_spritzguss(
        db,
        customer_id=int(cid),
        program_id=int(pid),
        project_id=int(prid),
        calculation_year=int(year) if year is not None else None,
    )
    payload.update(resolved)
    return payload


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
    data = body.model_dump(
        exclude={"veredelung_zuordnungen", "werk_id"},
    )
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
        schussgewicht_g=float(getattr(obj, "schussgewicht_g", 0) or 0),
        materialpreis_pro_kg=obj.materialpreis_pro_kg,
        ausschussquote_pct=obj.ausschussquote_pct,
        mgk_pct=obj.mgk_pct,
        material_nominierung=getattr(obj, "material_nominierung", None),  # type: ignore[arg-type]
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
        losgroesse=getattr(obj, "losgroesse", None),
        setup_zeit_min=float((obj.ergebnis or {}).get("setup_zeit_min", 0) or 0)
        if isinstance(obj.ergebnis, dict)
        else 0.0,
        setup_maschinenstundensatz=float(
            (obj.ergebnis or {}).get("setup_maschinenstundensatz", 0) or 0
        )
        if isinstance(obj.ergebnis, dict)
        else 0.0,
        setup_lohnstundensatz=float(
            (obj.ergebnis or {}).get("setup_lohnstundensatz", 0) or 0
        )
        if isinstance(obj.ergebnis, dict)
        else 0.0,
        setup_mitarbeiter=float((obj.ergebnis or {}).get("setup_mitarbeiter", 0) or 0)
        if isinstance(obj.ergebnis, dict)
        else 0.0,
        setup_aktiv=bool((obj.ergebnis or {}).get("setup_aktiv", False))
        if isinstance(obj.ergebnis, dict)
        else False,
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
            fgk_pct=0,
            reihenfolge=schritt.reihenfolge,
        )
    )
    return kosten.kosten_inkl_ausschuss


def _live_veredelung_kosten(schritt: Veredelungsschritt):
    return berechne_veredelung(
        VeredelungCalcInput(
            taktzeit_s=schritt.taktzeit_s,
            anzahl_mitarbeiter=schritt.anzahl_mitarbeiter,
            lohnstundensatz=schritt.lohnstundensatz,
            maschinenstundensatz=schritt.maschinenstundensatz,
            verbrauchskosten_je_stueck=schritt.verbrauchskosten_je_stueck,
            ausschussquote_pct=schritt.ausschussquote_pct,
            fgk_pct=0,
            reihenfolge=schritt.reihenfolge,
        )
    )


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
        live = _live_veredelung_kosten(schritt)
        if use_snapshots and snapshot is not None:
            kosten = snapshot.snapshot_kosten_inkl_ausschuss
            bezeichnung = snapshot.snapshot_bezeichnung
            art = snapshot.snapshot_veredelungsart
            # Ausbeutekette: Snapshot-Vor-Kosten/Quote (wie beim Speichern geschrieben).
            # Legacy-Zeilen ohne Vor-Snapshot → Live, damit Speichern = Berechnen.
            snap_vor = getattr(snapshot, "snapshot_kosten_vor_ausschuss", None)
            snap_q = getattr(snapshot, "snapshot_ausschussquote_pct", None)
            if snap_vor is not None and snap_q is not None:
                kosten_vor = float(snap_vor)
                ausschuss_q = float(snap_q)
            else:
                kosten_vor = live.kosten_vor_ausschuss
                ausschuss_q = float(schritt.ausschussquote_pct)
        else:
            kosten = live.kosten_inkl_ausschuss
            kosten_vor = live.kosten_vor_ausschuss
            ausschuss_q = float(schritt.ausschussquote_pct)
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
                kosten_vor_ausschuss=kosten_vor,
                ausschussquote_pct=ausschuss_q,
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


def _schema_mismatch_http(exc: ProgrammingError) -> HTTPException:
    """Übersetzt fehlende Snapshot-Spalten in eine handlungsfähige API-Antwort."""
    detail = (
        "Datenbankschema ist veraltet (fehlende Veredelungs-Snapshot-Spalten). "
        "Bitte `alembic upgrade head` ausführen "
        "(Revision e1a0007_veredelung_snapshot_yield)."
    )
    msg = str(getattr(exc, "orig", None) or exc)
    if "snapshot_kosten_vor_ausschuss" in msg or "snapshot_ausschussquote_pct" in msg:
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=detail)
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=(
            "Datenbankschema passt nicht zum API-Code (UndefinedColumn). "
            "Bitte `alembic upgrade head` ausführen."
        ),
    )


def _load_zuordnungen(db: Session, kalkulation_id: int) -> list[SpritzgussVeredelungZuordnung]:
    try:
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
    except ProgrammingError as exc:
        raise _schema_mismatch_http(exc) from exc


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
        live = _live_veredelung_kosten(schritt)
        row = SpritzgussVeredelungZuordnung(
            kalkulation_id=obj.id,
            veredelungsschritt_id=zuordnung.veredelungsschritt_id,
            reihenfolge=zuordnung.reihenfolge,
            aktiv=zuordnung.aktiv,
            mengenfaktor=zuordnung.mengenfaktor,
            snapshot_bezeichnung=schritt.bezeichnung,
            snapshot_veredelungsart=schritt.veredelungsart,
            snapshot_kosten_inkl_ausschuss=live.kosten_inkl_ausschuss,
            snapshot_kosten_vor_ausschuss=live.kosten_vor_ausschuss,
            snapshot_ausschussquote_pct=float(schritt.ausschussquote_pct),
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
    werk_id: int | None = None,
) -> SpritzgussCalcResponse:
    zuordnungen = _normalize_veredelung_zuordnungen(zuordnungen)
    calc_input = _apply_central_rates(db, calc_input, werk_id=werk_id)
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
            fgk_pct=calc_input.fgk_pct,
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
        # Gleiche Kostenbasis wie Endpreis: Gesamt-HK inkl. einer FGK
        "herstellkosten": gesamt.gesamte_herstellkosten,
        # Endpreis inkl. Veredelung und zentraler Zuschläge (nicht Spritzguss-VP allein)
        "verkaufspreis": gesamt.endpreis_je_stueck,
    }

    # FGK genau einmal und konsistent anzeigen (Basis inkl. Veredelung)
    bloecke["fertigung"] = {
        **bloecke.get("fertigung", {}),
        "maschinenkosten": gesamt.maschinenkosten,
        "fertigungslohn": gesamt.fertigungslohn,
        "setup_maschinenkosten_je_teil": gesamt.setup_maschinenkosten_je_teil,
        "setup_lohnkosten_je_teil": gesamt.setup_lohnkosten_je_teil,
        "setup_kosten_je_teil": gesamt.setup_kosten_je_teil,
        "fgk_basis": gesamt.fgk_basis,
        "fertigungsgemeinkosten": gesamt.fertigungsgemeinkosten,
        "fgk_pct": gesamt.applied_fgk_pct,
    }

    # FGK nur im Fertigungsblock (nicht nochmals unter Gemeinkosten) –
    # vermeidet den Eindruck einer zweiten Addition.
    bloecke["gemeinkosten"] = {
        "herstellkosten": gesamt.gesamte_herstellkosten,
        "vvgk": gesamt.vvgk,
        "vvgk_pct": gesamt.applied_vvgk_pct,
        "vvgk_basis": gesamt.gesamte_herstellkosten,
        "selbstkosten": gesamt.selbstkosten,
        "gewinn": gesamt.gewinn,
        "gewinn_pct": gesamt.applied_gewinn_pct,
        "gewinn_basis": gesamt.selbstkosten,
    }
    bloecke["verkaufspreis"] = {
        "nettoverkaufspreis": gesamt.nettoverkaufspreis,
        "skonto": gesamt.skonto,
        "skonto_pct": gesamt.applied_skonto_pct,
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
        werk_id=getattr(obj, "werk_id", None),
    )
    # Angewandte zentrale Sätze am Datensatz spiegeln (Export/Transparenz)
    ergebnis = response.ergebnis
    if ergebnis.applied_mgk_pct is not None:
        obj.mgk_pct = float(ergebnis.applied_mgk_pct)
    if ergebnis.applied_fgk_pct is not None:
        obj.fgk_pct = float(ergebnis.applied_fgk_pct)
    if ergebnis.applied_vvgk_pct is not None:
        obj.vvgk_pct = float(ergebnis.applied_vvgk_pct)
    if ergebnis.applied_gewinn_pct is not None:
        obj.gewinn_pct = float(ergebnis.applied_gewinn_pct)
    if ergebnis.applied_skonto_pct is not None:
        obj.skonto_pct = float(ergebnis.applied_skonto_pct)
    if ergebnis.material_nominierung is not None:
        obj.material_nominierung = ergebnis.material_nominierung
    previous = obj.ergebnis if isinstance(obj.ergebnis, dict) else {}
    dumped = ergebnis.model_dump()
    # Setup-Eingabeparameter beibehalten / aus calc_input spiegeln
    calc_in = _to_calc_input_from_model(obj)
    for key in (
        "setup_zeit_min",
        "setup_maschinenstundensatz",
        "setup_lohnstundensatz",
        "setup_mitarbeiter",
        "setup_aktiv",
    ):
        dumped[key] = getattr(calc_in, key, previous.get(key, 0 if key != "setup_aktiv" else False))
    # Maschinenrate-Snapshot (falls Maschine verknüpft)
    rate_snap = previous.get("maschinen_rate_snapshot")
    if obj.maschine_id:
        maschine = db.get(Maschine, obj.maschine_id)
        if maschine is not None:
            rate_snap = {
                "maschine_id": maschine.id,
                "maschinen_nr": maschine.maschinen_nr,
                "source_currency": maschine.source_currency,
                "stundensatz_source": maschine.stundensatz_source,
                "stundensatz_eur": maschine.stundensatz,
                "jahresstunden": maschine.jahresstunden,
                "komponenten_usd": {
                    "space": maschine.space_costs_pro_stunde,
                    "abschreibung": maschine.abschreibung_pro_stunde,
                    "zinsen": maschine.zinsen_pro_stunde,
                    "versicherung": maschine.versicherung_pro_stunde,
                    "instandhaltung": maschine.instandhaltung_pro_stunde,
                    "energie": maschine.energie_pro_stunde,
                },
                "fx_to_eur": None,
                "werk_id": maschine.werk_id,
            }
            if maschine.werk_id:
                werk = db.get(Werk, maschine.werk_id)
                if werk:
                    rate_snap["fx_to_eur"] = float(werk.fx_to_eur)
                    rate_snap["currency"] = werk.currency
                    rate_snap["werk_code"] = werk.code
    if rate_snap:
        dumped["maschinen_rate_snapshot"] = rate_snap
    if getattr(obj, "werk_id", None):
        werk = db.get(Werk, obj.werk_id)
        if werk:
            dumped["werk_snapshot"] = {
                "werk_id": werk.id,
                "code": werk.code,
                "name": werk.name,
                "currency": werk.currency,
                "fx_to_eur": float(werk.fx_to_eur),
            }
    obj.ergebnis = dumped
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
    erg = obj.ergebnis if isinstance(obj.ergebnis, dict) else {}
    return base.model_copy(
        update={
            "veredelung_zuordnungen": zuordnungen,
            "setup_zeit_min": float(erg.get("setup_zeit_min", 0) or 0),
            "setup_maschinenstundensatz": float(
                erg.get("setup_maschinenstundensatz", 0) or 0
            ),
            "setup_lohnstundensatz": float(erg.get("setup_lohnstundensatz", 0) or 0),
            "setup_mitarbeiter": float(erg.get("setup_mitarbeiter", 0) or 0),
            "setup_aktiv": bool(erg.get("setup_aktiv", False)),
        }
    )


def _run_calculation(
    db: Session,
    calc_input: SpritzgussInput,
    zuordnungen: list[VeredelungZuordnungInput],
    *,
    werk_id: int | None = None,
) -> SpritzgussCalcResponse:
    return _build_calc_response(
        db, calc_input, zuordnungen, use_snapshots=False, werk_id=werk_id
    )


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
        werk_id=body.werk_id,
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
    live = _live_veredelung_kosten(schritt)
    row = SpritzgussVeredelungZuordnung(
        kalkulation_id=item_id,
        veredelungsschritt_id=body.veredelungsschritt_id,
        reihenfolge=body.reihenfolge,
        aktiv=body.aktiv,
        mengenfaktor=body.mengenfaktor,
        snapshot_bezeichnung=schritt.bezeichnung,
        snapshot_veredelungsart=schritt.veredelungsart,
        snapshot_kosten_inkl_ausschuss=live.kosten_inkl_ausschuss,
        snapshot_kosten_vor_ausschuss=live.kosten_vor_ausschuss,
        snapshot_ausschussquote_pct=float(schritt.ausschussquote_pct),
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


SETUP_ERGEBNIS_KEYS = (
    "setup_zeit_min",
    "setup_maschinenstundensatz",
    "setup_lohnstundensatz",
    "setup_mitarbeiter",
    "setup_aktiv",
)


def _merge_setup_into_ergebnis(obj: SpritzgussKalkulation, setup: dict[str, Any]) -> None:
    current = dict(obj.ergebnis) if isinstance(obj.ergebnis, dict) else {}
    for key in SETUP_ERGEBNIS_KEYS:
        if key in setup and setup[key] is not None:
            current[key] = setup[key]
    obj.ergebnis = current


@router.post("", response_model=SpritzgussKalkulationRead, status_code=status.HTTP_201_CREATED)
def create_kalkulation(
    body: SpritzgussKalkulationCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    zuordnungen = body.veredelung_zuordnungen
    payload = body.model_dump(exclude={"veredelung_zuordnungen", *SETUP_ERGEBNIS_KEYS})
    payload = _apply_hierarchy_payload(db, payload)
    if payload.get("werkzeug_abrechnungsart") == "einmalzahlung":
        payload["amortisationsvolumen"] = None
    obj = SpritzgussKalkulation(**payload)
    db.add(obj)
    db.flush()
    _merge_setup_into_ergebnis(
        obj,
        {k: getattr(body, k) for k in SETUP_ERGEBNIS_KEYS},
    )
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
    setup_updates = {k: updates.pop(k) for k in list(SETUP_ERGEBNIS_KEYS) if k in updates}
    if setup_updates:
        _merge_setup_into_ergebnis(obj, setup_updates)
    hierarchy_keys = {"customer_id", "program_id", "project_id", "calculation_year"}
    if hierarchy_keys.intersection(updates):
        merged = {
            "customer_id": updates.get("customer_id", obj.customer_id),
            "program_id": updates.get("program_id", obj.program_id),
            "project_id": updates.get("project_id", obj.project_id),
            "calculation_year": updates.get("calculation_year", obj.calculation_year),
        }
        merged = _apply_hierarchy_payload(db, merged)
        updates.update(merged)
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
    """Löscht eine Spritzguss-Kalkulation inkl. abhängiger Veredelungs-/Investitionsdaten.

    Referenzen in Baugruppen (Legacy-Zuordnung oder Assembly-PART) blockieren das
    Löschen bewusst (FK NO ACTION / RESTRICT) – dann HTTP 409 mit Hinweis.
    """
    obj = db.get(SpritzgussKalkulation, item_id)
    if not obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Kalkulation nicht gefunden"
        )

    blockers: list[str] = []

    assembly_count = db.scalar(
        select(func.count())
        .select_from(AssemblyPosition)
        .where(AssemblyPosition.part_calculation_id == item_id)
    )
    if assembly_count:
        blockers.append(
            f"{assembly_count} Baugruppen-Position(en) (assembly_positions)"
        )

    legacy_count = db.scalar(
        select(func.count())
        .select_from(BaugruppeSpritzgussZuordnung)
        .where(BaugruppeSpritzgussZuordnung.spritzguss_kalkulation_id == item_id)
    )
    if legacy_count:
        blockers.append(
            f"{legacy_count} Legacy-Baugruppen-Zuordnung(en)"
        )

    if blockers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Kalkulation kann nicht gelöscht werden, weil sie noch in Baugruppen "
                "verwendet wird (aktiv oder archiviert): "
                + "; ".join(blockers)
                + ". Bitte zuerst die Verknüpfungen in den betreffenden Baugruppen entfernen "
                "oder die Baugruppe endgültig löschen."
            ),
        )

    # Abhängigkeiten, die mit der Kalkulation entfallen dürfen
    for verd in db.scalars(
        select(SpritzgussVeredelungZuordnung).where(
            SpritzgussVeredelungZuordnung.kalkulation_id == item_id
        )
    ).all():
        db.delete(verd)
    for inv in db.scalars(
        select(Investition).where(Investition.calculation_id == item_id)
    ).all():
        db.delete(inv)

    db.delete(obj)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Kalkulation kann nicht gelöscht werden, weil noch abhängige "
                "Datensätze darauf verweisen. Bitte Verknüpfungen in Baugruppen "
                "prüfen und entfernen."
            ),
        ) from exc

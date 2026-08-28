from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.permissions import require_kalkulator, require_viewer
from app.database import get_db
from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import (
    Baugruppe,
    BaugruppeKaufteilZuordnung,
    BaugruppeSpritzgussZuordnung,
    BaugruppeVeredelungZuordnung,
)
from app.models.investition import Investition
from app.models.kaufteil import Kaufteil
from app.models.program import Program
from app.models.project import Project
from app.models.customer import Customer
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.user import User
from app.models.veredelungsschritt import Veredelungsschritt
from app.schemas.baugruppe import (
    BaugruppeCalcRequest,
    BaugruppeCalcResponse,
    BaugruppeCreate,
    BaugruppeErgebnisSchema,
    BaugruppeListItem,
    BaugruppeRead,
    BaugruppeUpdate,
    InvestitionRead,
    KaufteilZuordnungInput,
    KaufteilZuordnungRead,
    SpritzgussZuordnungInput,
    SpritzgussZuordnungRead,
    VeredelungZuordnungInput,
    VeredelungZuordnungRead,
)
from app.services.baugruppe_kalkulation import (
    BaugruppeMarkupError,
    BaugruppeValidationError,
    EinzelteilEingabe,
    InvestitionAnzeige,
    KaufteilEingabe,
    VeredelungEingabe,
    berechne_baugruppe,
)
from app.services.investition_financials import effective_cost_amount, financial_fields_for_export
from app.services.spritzguss_cost_snapshot import selbstkosten_aus_ergebnis
from app.services.central_markup_rates import (
    CentralMarkupRatesError,
    load_central_markup_rates,
)
from app.services.kaufteil_kalkulation import KaufteilKalkulationError, berechne_kaufteil_kosten
from app.services.project_volume_service import average_jahresstueckzahl_for_project
from app.services.veredelung_kalkulation import VeredelungInput as VeredelungCalcInput
from app.services.veredelung_kalkulation import VeredelungValidationError, berechne_veredelung
from decimal import Decimal, ROUND_HALF_UP

router = APIRouter(prefix="/baugruppen", tags=["Baugruppen"])


def _money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _kaufteil_kosten_detail(
    db: Session,
    kt: Kaufteil,
    *,
    werk_id: int | None = None,
    einkauf_override: float | None = None,
):
    """Volle Kaufteilkosten je Stück inkl. MGK, OEM-Handling und SG&A."""
    try:
        rates = load_central_markup_rates(db, werk_id=werk_id)
        return berechne_kaufteil_kosten(
            einkauf_override if einkauf_override is not None else kt.preis,
            kt.nominierung,
            rates,
            sga_override_aktiv=bool(getattr(kt, "sga_override_aktiv", False)),
            sga_satz_manuell=getattr(kt, "sga_satz_manuell", None),
            kontext=f"Kaufteil '{kt.bezeichnung}'",
        )
    except (CentralMarkupRatesError, KaufteilKalkulationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc


def _kaufteil_preis_inkl_overheads(
    db: Session, kt: Kaufteil, *, werk_id: int | None = None, einkauf_override: float | None = None
) -> float:
    detail = _kaufteil_kosten_detail(
        db, kt, werk_id=werk_id, einkauf_override=einkauf_override
    )
    return float(detail.kosten_inkl_overheads_je_stueck)


def _selbstkosten_aus_spritzguss(kalk: SpritzgussKalkulation) -> float:
    ergebnis = kalk.ergebnis if isinstance(kalk.ergebnis, dict) else None
    selbstkosten = selbstkosten_aus_ergebnis(ergebnis)
    if selbstkosten is not None:
        return _money(selbstkosten)
    return 0.0


def _veredelung_direktkosten(schritt: Veredelungsschritt) -> tuple[float, float, float, float, float]:
    """Direkte Montagekosten je Stück vor Assembly-Ausschuss (ohne FGK)."""
    try:
        result = berechne_veredelung(
            VeredelungCalcInput(
                taktzeit_s=schritt.taktzeit_s,
                anzahl_mitarbeiter=schritt.anzahl_mitarbeiter,
                lohnstundensatz=schritt.lohnstundensatz,
                maschinenstundensatz=schritt.maschinenstundensatz,
                verbrauchskosten_je_stueck=schritt.verbrauchskosten_je_stueck,
                ausschussquote_pct=0.0,
                fgk_pct=0.0,
                reihenfolge=schritt.reihenfolge,
            )
        )
    except VeredelungValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Veredelungsschritt '{schritt.bezeichnung}': {exc}",
        ) from exc
    return (
        result.lohnkosten_je_stueck,
        result.maschinenkosten_je_stueck,
        result.verbrauchskosten_je_stueck,
        result.kosten_vor_ausschuss,
        float(schritt.ausschussquote_pct),
    )


def _endpreis_aus_spritzguss(kalk: SpritzgussKalkulation) -> float:
    """Legacy-Alias: Baugruppe nutzt Selbstkosten, nicht Verkaufspreis."""
    return _selbstkosten_aus_spritzguss(kalk)


def _normalize_spritzguss_zuordnungen(
    items: list[SpritzgussZuordnungInput | dict[str, Any]] | None,
) -> list[SpritzgussZuordnungInput]:
    if not items:
        return []
    result: list[SpritzgussZuordnungInput] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, SpritzgussZuordnungInput):
            result.append(item)
        elif isinstance(item, dict):
            try:
                result.append(SpritzgussZuordnungInput.model_validate(item))
            except ValidationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Einzelteil-Zuordnung #{index}: {exc.errors()[0]['msg']}",
                ) from exc
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Einzelteil-Zuordnung #{index}: ungültiges Format",
            )
    return result


def _normalize_kaufteil_zuordnungen(
    items: list[KaufteilZuordnungInput | dict[str, Any]] | None,
) -> list[KaufteilZuordnungInput]:
    if not items:
        return []
    result: list[KaufteilZuordnungInput] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, KaufteilZuordnungInput):
            result.append(item)
        elif isinstance(item, dict):
            try:
                result.append(KaufteilZuordnungInput.model_validate(item))
            except ValidationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Kaufteil-Zuordnung #{index}: {exc.errors()[0]['msg']}",
                ) from exc
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Kaufteil-Zuordnung #{index}: ungültiges Format",
            )
    return result


def _normalize_veredelung_zuordnungen(
    items: list[VeredelungZuordnungInput | dict[str, Any]] | None,
) -> list[VeredelungZuordnungInput]:
    if not items:
        return []
    result: list[VeredelungZuordnungInput] = []
    for index, item in enumerate(items, start=1):
        if isinstance(item, VeredelungZuordnungInput):
            result.append(item)
        elif isinstance(item, dict):
            payload = dict(item)
            if "sequence" in payload and "reihenfolge" not in payload:
                payload["reihenfolge"] = payload.pop("sequence")
            if "quantity_factor" in payload and "mengenfaktor" not in payload:
                payload["mengenfaktor"] = payload.pop("quantity_factor")
            try:
                result.append(VeredelungZuordnungInput.model_validate(payload))
            except ValidationError as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"Veredelungs-Zuordnung #{index}: {exc.errors()[0]['msg']}",
                ) from exc
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Veredelungs-Zuordnung #{index}: ungültiges Format",
            )
    return result


def _validate_zuordnungen_project_scope(
    db: Session,
    project_id: int | None,
    spritzguss_zuordnungen: list[SpritzgussZuordnungInput],
    kaufteil_zuordnungen: list[KaufteilZuordnungInput],
    *,
    allow_inactive_spritzguss_ids: set[int] | None = None,
    allow_inactive_kaufteil_ids: set[int] | None = None,
) -> None:
    """Erzwingt Projektübereinstimmung; Kaufteile dürfen projektbezogen oder Standard sein."""
    if project_id is None:
        return
    allow_sg = allow_inactive_spritzguss_ids or set()
    allow_kt = allow_inactive_kaufteil_ids or set()

    for index, z in enumerate(spritzguss_zuordnungen, start=1):
        kalk = db.get(SpritzgussKalkulation, z.spritzguss_kalkulation_id)
        if not kalk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Einzelteil-Zuordnung #{index}: Spritzguss-Kalkulation nicht gefunden",
            )
        if kalk.project_id != project_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Einzelteil-Zuordnung #{index}: Kalkulation gehört nicht zum "
                    f"Projekt der Baugruppe (project_id={project_id})"
                ),
            )
        if not kalk.aktiv and kalk.id not in allow_sg:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Einzelteil-Zuordnung #{index}: inaktive Kalkulation nicht auswählbar",
            )

    for index, z in enumerate(kaufteil_zuordnungen, start=1):
        kt = db.get(Kaufteil, z.kaufteil_id)
        if not kt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Kaufteil-Zuordnung #{index}: Kaufteil nicht gefunden",
            )
        if kt.project_id is not None and kt.project_id != project_id:
            if z.kaufteil_id not in allow_kt:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Kaufteil-Zuordnung #{index}: Kaufteil gehört nicht zum "
                        f"Projekt der Baugruppe (project_id={project_id})"
                    ),
                )
        if not kt.aktiv and kt.id not in allow_kt:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Kaufteil-Zuordnung #{index}: inaktives Kaufteil nicht auswählbar",
            )


def _load_investitionen(
    db: Session,
    baugruppe_id: int | None,
    spritzguss_ids: list[int],
) -> list[InvestitionAnzeige]:
    rows: list[Investition] = []
    if baugruppe_id is not None:
        rows.extend(
            db.scalars(
                select(Investition).where(Investition.baugruppe_id == baugruppe_id)
            ).all()
        )
    if spritzguss_ids:
        rows.extend(
            db.scalars(
                select(Investition).where(Investition.calculation_id.in_(spritzguss_ids))
            ).all()
        )
    seen: set[int] = set()
    result: list[InvestitionAnzeige] = []
    for inv in rows:
        if inv.id in seen:
            continue
        seen.add(inv.id)
        quelle = "Baugruppe" if inv.baugruppe_id else "Einzelteil"
        cost = effective_cost_amount(
            cost_amount=getattr(inv, "cost_amount", None),
            amount=inv.amount,
        )
        fin = financial_fields_for_export(
            cost_amount=getattr(inv, "cost_amount", None),
            bottom_price=getattr(inv, "bottom_price", None),
            revenue_amount=getattr(inv, "revenue_amount", None),
            legacy_amount=inv.amount,
        )
        result.append(
            InvestitionAnzeige(
                id=inv.id,
                bezeichnung=inv.name or inv.description or inv.part_name,
                investment_type=inv.investment_type,
                amount=float(cost),
                status=inv.status,
                quelle=quelle,
                cost_amount=fin["cost_amount"],
                bottom_price=fin["bottom_price"],
                revenue_amount=fin["revenue_amount"],
            )
        )
    return result


def _resolve_eingaben(
    db: Session,
    spritzguss_zuordnungen: list[SpritzgussZuordnungInput],
    kaufteil_zuordnungen: list[KaufteilZuordnungInput],
    veredelung_zuordnungen: list[VeredelungZuordnungInput],
    *,
    use_snapshots: bool,
    baugruppe_id: int | None = None,
    werk_id: int | None = None,
) -> tuple[list[EinzelteilEingabe], list[KaufteilEingabe], list[VeredelungEingabe]]:
    sg_snap: dict[int, BaugruppeSpritzgussZuordnung] = {}
    kt_snap: dict[int, BaugruppeKaufteilZuordnung] = {}
    vd_snap: dict[int, BaugruppeVeredelungZuordnung] = {}
    if use_snapshots and baugruppe_id is not None:
        sg_snap = {
            r.spritzguss_kalkulation_id: r
            for r in db.scalars(
                select(BaugruppeSpritzgussZuordnung).where(
                    BaugruppeSpritzgussZuordnung.baugruppe_id == baugruppe_id
                )
            ).all()
        }
        kt_snap = {
            r.kaufteil_id: r
            for r in db.scalars(
                select(BaugruppeKaufteilZuordnung).where(
                    BaugruppeKaufteilZuordnung.baugruppe_id == baugruppe_id
                )
            ).all()
        }
        vd_snap = {
            r.veredelungsschritt_id: r
            for r in db.scalars(
                select(BaugruppeVeredelungZuordnung).where(
                    BaugruppeVeredelungZuordnung.baugruppe_id == baugruppe_id
                )
            ).all()
        }

    einzelteile: list[EinzelteilEingabe] = []
    for z in spritzguss_zuordnungen:
        kalk = db.get(SpritzgussKalkulation, z.spritzguss_kalkulation_id)
        if not kalk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Spritzguss-Kalkulation {z.spritzguss_kalkulation_id} nicht gefunden",
            )
        snap = sg_snap.get(z.spritzguss_kalkulation_id)
        if use_snapshots and snap is not None:
            preis = snap.snapshot_preis
            bezeichnung = snap.snapshot_bezeichnung
            teilenummer = snap.snapshot_teilenummer
        else:
            preis = _endpreis_aus_spritzguss(kalk)
            bezeichnung = kalk.teilebezeichnung
            teilenummer = kalk.teilenummer
        einzelteile.append(
            EinzelteilEingabe(
                spritzguss_kalkulation_id=z.spritzguss_kalkulation_id,
                bezeichnung=bezeichnung,
                teilenummer=teilenummer,
                menge=z.menge,
                reihenfolge=z.reihenfolge,
                snapshot_preis=preis,
            )
        )

    kaufteile: list[KaufteilEingabe] = []
    for z in kaufteil_zuordnungen:
        kt = db.get(Kaufteil, z.kaufteil_id)
        if not kt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Kaufteil {z.kaufteil_id} nicht gefunden",
            )
        snap = kt_snap.get(z.kaufteil_id)
        detail = _kaufteil_kosten_detail(
            db,
            kt,
            werk_id=werk_id,
        )
        unit_total = float(detail.kosten_inkl_overheads_je_stueck)
        if use_snapshots and snap is not None:
            # Gespeicherter Snapshot = Kosten inkl. Overheads je Stück (nicht Einkaufspreis).
            unit_total = float(snap.snapshot_preis)
        bezeichnung = snap.snapshot_bezeichnung if snap else kt.bezeichnung
        lieferant = snap.snapshot_lieferant if snap else kt.lieferant
        kaufteile.append(
            KaufteilEingabe(
                kaufteil_id=z.kaufteil_id,
                bezeichnung=bezeichnung,
                lieferant=lieferant,
                menge=z.menge,
                reihenfolge=z.reihenfolge,
                nominierung=detail.nominierung,
                einkaufspreis_je_stueck=float(detail.einkaufspreis_je_stueck),
                mgk_satz_pct=float(detail.mgk_satz_pct),
                mgk_je_stueck=float(detail.mgk_je_stueck),
                oem_handling_satz_pct=float(detail.oem_handling_satz_pct),
                oem_handling_je_stueck=float(detail.oem_handling_je_stueck),
                sga_satz_pct=float(detail.sga_satz_pct),
                sga_quelle=detail.sga_quelle,
                sga_je_stueck=float(detail.sga_je_stueck),
                kosten_inkl_overheads_je_stueck=unit_total,
            )
        )

    veredelungen: list[VeredelungEingabe] = []
    for z in veredelung_zuordnungen:
        schritt = db.get(Veredelungsschritt, z.veredelungsschritt_id)
        if not schritt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Veredelungsschritt {z.veredelungsschritt_id} nicht gefunden",
            )
        snap = vd_snap.get(z.veredelungsschritt_id)
        if use_snapshots and snap is not None:
            bezeichnung = snap.snapshot_bezeichnung
            lohn, maschine, verbrauch, direkt, ausschussquote_pct = _veredelung_direktkosten(schritt)
        else:
            lohn, maschine, verbrauch, direkt, ausschussquote_pct = _veredelung_direktkosten(schritt)
            bezeichnung = schritt.bezeichnung
        veredelungen.append(
            VeredelungEingabe(
                veredelungsschritt_id=z.veredelungsschritt_id,
                bezeichnung=bezeichnung,
                reihenfolge=z.reihenfolge,
                mengenfaktor=z.mengenfaktor,
                ausschussquote_pct=ausschussquote_pct,
                lohnkosten_je_stueck=lohn,
                maschinenkosten_je_stueck=maschine,
                verbrauchskosten_je_stueck=verbrauch,
                direktkosten_je_stueck=direkt,
            )
        )

    return einzelteile, kaufteile, veredelungen


def _build_calc_response(
    db: Session,
    *,
    name: str,
    jahresstueckzahl: int,
    spritzguss_zuordnungen: list[SpritzgussZuordnungInput | dict[str, Any]],
    kaufteil_zuordnungen: list[KaufteilZuordnungInput | dict[str, Any]],
    veredelung_zuordnungen: list[VeredelungZuordnungInput | dict[str, Any]],
    use_snapshots: bool = False,
    baugruppe_id: int | None = None,
    werk_id: int | None = None,
    project_id: int | None = None,
    allow_inactive_spritzguss_ids: set[int] | None = None,
    allow_inactive_kaufteil_ids: set[int] | None = None,
) -> BaugruppeCalcResponse:
    if not name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Baugruppenname ist erforderlich",
        )
    sg = _normalize_spritzguss_zuordnungen(spritzguss_zuordnungen)
    kt = _normalize_kaufteil_zuordnungen(kaufteil_zuordnungen)
    vd = _normalize_veredelung_zuordnungen(veredelung_zuordnungen)

    effective_project_id = project_id
    if effective_project_id is None and baugruppe_id is not None:
        bg = db.get(Baugruppe, baugruppe_id)
        if bg:
            effective_project_id = _effective_project_id(bg)

    _validate_zuordnungen_project_scope(
        db,
        effective_project_id,
        sg,
        kt,
        allow_inactive_spritzguss_ids=allow_inactive_spritzguss_ids,
        allow_inactive_kaufteil_ids=allow_inactive_kaufteil_ids,
    )

    try:
        rates = load_central_markup_rates(db, werk_id=werk_id)
        gewinn_pct = rates.gewinn_pct
        fgk_pct = rates.fgk_pct
    except CentralMarkupRatesError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    try:
        einzelteile, kaufteile, veredelungen = _resolve_eingaben(
            db,
            sg,
            kt,
            vd,
            use_snapshots=use_snapshots,
            baugruppe_id=baugruppe_id,
            werk_id=werk_id,
        )
        investitionen = _load_investitionen(
            db,
            baugruppe_id,
            [e.spritzguss_kalkulation_id for e in einzelteile],
        )
        ergebnis = berechne_baugruppe(
            einzelteile,
            kaufteile,
            veredelungen,
            jahresstueckzahl=jahresstueckzahl,
            investitionen=investitionen,
            gewinn_pct=gewinn_pct,
            fgk_pct=fgk_pct,
        )
    except BaugruppeMarkupError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except BaugruppeValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    bloecke = {
        "zusammenfassung": ergebnis.as_zusammenfassung(),
        "einzelteile": {f"position_{i + 1}": p.zwischensumme for i, p in enumerate(ergebnis.einzelteile)},
        "kaufteile": {f"position_{i + 1}": p.zwischensumme for i, p in enumerate(ergebnis.kaufteile)},
        "veredelung": {f"schritt_{v.reihenfolge}": v.direktkosten for v in ergebnis.veredelungen},
        "ueberleitung": {
            "vorprodukt": ergebnis.vorprodukt_gesamt,
            "assembly_direkt": ergebnis.assembly_direkt_gesamt,
            "assembly_fgk_basis": ergebnis.assembly_fgk_basis,
            "assembly_fgk": ergebnis.assembly_fgk_betrag,
            "kostenbasis_vor_ausschuss": ergebnis.kostenbasis_vor_ausschuss,
            "assembly_ausschuss": ergebnis.assembly_ausschuss_zuschlag,
            "kostenbasis_nach_assembly": ergebnis.kostenbasis_nach_assembly,
            "gewinn_pct": ergebnis.gewinn_pct,
            "gewinn_betrag": ergebnis.gewinn_betrag,
            "endpreis": ergebnis.baugruppenpreis_je_stueck,
        },
        "investitionen": {f"inv_{i.id}": i.amount for i in ergebnis.investitionen},
    }

    return BaugruppeCalcResponse(
        ergebnis=BaugruppeErgebnisSchema(**ergebnis.to_dict()),
        bloecke=bloecke,
    )


def _sync_spritzguss_zuordnungen(
    db: Session,
    obj: Baugruppe,
    zuordnungen: list[SpritzgussZuordnungInput | dict[str, Any]],
) -> None:
    zuordnungen = _normalize_spritzguss_zuordnungen(zuordnungen)
    for row in db.scalars(
        select(BaugruppeSpritzgussZuordnung).where(
            BaugruppeSpritzgussZuordnung.baugruppe_id == obj.id
        )
    ).all():
        db.delete(row)
    db.flush()
    for z in zuordnungen:
        kalk = db.get(SpritzgussKalkulation, z.spritzguss_kalkulation_id)
        if not kalk:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Spritzguss-Kalkulation {z.spritzguss_kalkulation_id} nicht gefunden",
            )
        db.add(
            BaugruppeSpritzgussZuordnung(
                baugruppe_id=obj.id,
                spritzguss_kalkulation_id=z.spritzguss_kalkulation_id,
                menge=z.menge,
                reihenfolge=z.reihenfolge,
                snapshot_preis=_selbstkosten_aus_spritzguss(kalk),
                snapshot_bezeichnung=kalk.teilebezeichnung,
                snapshot_teilenummer=kalk.teilenummer,
            )
        )
    db.flush()


def _sync_kaufteil_zuordnungen(
    db: Session,
    obj: Baugruppe,
    zuordnungen: list[KaufteilZuordnungInput | dict[str, Any]],
) -> None:
    zuordnungen = _normalize_kaufteil_zuordnungen(zuordnungen)
    for row in db.scalars(
        select(BaugruppeKaufteilZuordnung).where(
            BaugruppeKaufteilZuordnung.baugruppe_id == obj.id
        )
    ).all():
        db.delete(row)
    db.flush()
    for z in zuordnungen:
        kt = db.get(Kaufteil, z.kaufteil_id)
        if not kt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Kaufteil {z.kaufteil_id} nicht gefunden",
            )
        preis = (
            z.snapshot_preis
            if z.snapshot_preis is not None
            else _kaufteil_preis_inkl_overheads(
                db, kt, werk_id=getattr(obj, "werk_id", None)
            )
        )
        db.add(
            BaugruppeKaufteilZuordnung(
                baugruppe_id=obj.id,
                kaufteil_id=z.kaufteil_id,
                menge=z.menge,
                reihenfolge=z.reihenfolge,
                snapshot_preis=preis,
                snapshot_bezeichnung=kt.bezeichnung,
                snapshot_lieferant=kt.lieferant,
            )
        )
    db.flush()


def _sync_veredelung_zuordnungen(
    db: Session,
    obj: Baugruppe,
    zuordnungen: list[VeredelungZuordnungInput | dict[str, Any]],
) -> None:
    zuordnungen = _normalize_veredelung_zuordnungen(zuordnungen)
    for row in db.scalars(
        select(BaugruppeVeredelungZuordnung).where(
            BaugruppeVeredelungZuordnung.baugruppe_id == obj.id
        )
    ).all():
        db.delete(row)
    db.flush()
    for z in zuordnungen:
        schritt = db.get(Veredelungsschritt, z.veredelungsschritt_id)
        if not schritt:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Veredelungsschritt {z.veredelungsschritt_id} nicht gefunden",
            )
        lohn, maschine, verbrauch, kosten_vor_ausschuss, _ = _veredelung_direktkosten(schritt)
        db.add(
            BaugruppeVeredelungZuordnung(
                baugruppe_id=obj.id,
                veredelungsschritt_id=z.veredelungsschritt_id,
                reihenfolge=z.reihenfolge,
                mengenfaktor=z.mengenfaktor,
                snapshot_kosten=kosten_vor_ausschuss,
                snapshot_bezeichnung=schritt.bezeichnung,
            )
        )
    db.flush()


def _apply_calculation(db: Session, obj: Baugruppe) -> BaugruppeCalcResponse:
    sg_rows = list(
        db.scalars(
            select(BaugruppeSpritzgussZuordnung)
            .where(BaugruppeSpritzgussZuordnung.baugruppe_id == obj.id)
            .order_by(BaugruppeSpritzgussZuordnung.reihenfolge)
        ).all()
    )
    kt_rows = list(
        db.scalars(
            select(BaugruppeKaufteilZuordnung)
            .where(BaugruppeKaufteilZuordnung.baugruppe_id == obj.id)
            .order_by(BaugruppeKaufteilZuordnung.reihenfolge)
        ).all()
    )
    vd_rows = list(
        db.scalars(
            select(BaugruppeVeredelungZuordnung)
            .where(BaugruppeVeredelungZuordnung.baugruppe_id == obj.id)
            .order_by(BaugruppeVeredelungZuordnung.reihenfolge)
        ).all()
    )
    response = _build_calc_response(
        db,
        name=obj.name,
        jahresstueckzahl=obj.jahresstueckzahl,
        spritzguss_zuordnungen=[
            SpritzgussZuordnungInput(
                spritzguss_kalkulation_id=r.spritzguss_kalkulation_id,
                menge=r.menge,
                reihenfolge=r.reihenfolge,
            )
            for r in sg_rows
        ],
        kaufteil_zuordnungen=[
            KaufteilZuordnungInput(
                kaufteil_id=r.kaufteil_id,
                menge=r.menge,
                reihenfolge=r.reihenfolge,
                snapshot_preis=r.snapshot_preis,
            )
            for r in kt_rows
        ],
        veredelung_zuordnungen=[
            VeredelungZuordnungInput(
                veredelungsschritt_id=r.veredelungsschritt_id,
                reihenfolge=r.reihenfolge,
                mengenfaktor=r.mengenfaktor,
            )
            for r in vd_rows
        ],
        use_snapshots=True,
        baugruppe_id=obj.id,
        werk_id=getattr(obj, "werk_id", None),
        project_id=_effective_project_id(obj),
        allow_inactive_spritzguss_ids={r.spritzguss_kalkulation_id for r in sg_rows},
        allow_inactive_kaufteil_ids={r.kaufteil_id for r in kt_rows},
    )
    obj.ergebnis = response.ergebnis.model_dump()
    obj.ergebnis_bloecke = response.bloecke
    return response


def _resolve_customer_id_for_project(db: Session, project_id: int | None) -> int | None:
    if project_id is None:
        return None
    project = db.get(Project, project_id)
    if not project or getattr(project, "program_id", None) is None:
        return None
    program = db.get(Program, project.program_id)
    return program.customer_id if program else None


def _resolve_program_id_for_project(db: Session, project_id: int | None) -> int | None:
    if project_id is None:
        return None
    project = db.get(Project, project_id)
    return project.program_id if project else None


def _effective_project_id(obj: Baugruppe) -> int | None:
    """Bevorzugt project_id, fällt auf linked_project_id zurück (Übergangsdaten)."""
    if obj.project_id is not None:
        return obj.project_id
    return obj.linked_project_id


def _apply_jahresstueckzahl_from_project(
    db: Session,
    payload: dict[str, Any],
    *,
    existing_project_id: int | None = None,
    existing_jahresstueckzahl: int | None = None,
    project_changed: bool,
    clear_project_link: bool = False,
) -> dict[str, Any]:
    """Setzt jahresstueckzahl aus dem Projekt-Durchschnitt (ceil), wenn fachlich nötig.

    Entscheidung (keine Migration bestehender Daten ungefragt):
    - Create/Update mit Projektwechsel + Volumen: Wert aus Durchschnitt speichern.
    - Create mit Projekt ohne Volumen: 0 speichern (FE zeigt Hinweis).
    - Update bei Projektwechsel ohne Volumen: bestehenden Wert behalten.
    - Update ohne Projektwechsel: Client-jahresstueckzahl ignorieren (kein Override).
    - Verknüpfung entfernt: gespeicherten Wert belassen.
    - Legacy ohne Projekt: Client-jahresstueckzahl unverändert (Maske ist read-only;
      API bleibt für Bestandswerte speicherbar).
    """
    if clear_project_link:
        payload.pop("jahresstueckzahl", None)
        return payload

    project_id = payload.get("project_id")
    if project_id is None:
        # Kein Projektbezug in diesem Payload → keine serverseitige Ableitung
        return payload

    # Mit Projekt: Client darf den Wert nicht überschreiben
    payload.pop("jahresstueckzahl", None)

    if not project_changed and existing_project_id is not None:
        return payload

    avg = average_jahresstueckzahl_for_project(db, int(project_id))
    if avg.jahresstueckzahl is not None:
        payload["jahresstueckzahl"] = avg.jahresstueckzahl
    elif existing_jahresstueckzahl is None:
        payload["jahresstueckzahl"] = 0
    return payload


def _apply_project_to_baugruppe_payload(
    db: Session,
    payload: dict[str, Any],
    *,
    existing_project_id: int | None = None,
    clear_project_link: bool = False,
) -> dict[str, Any]:
    """Setzt project_id/linked_project_id und denormalisiert kunde/projekt aus Stammdaten.

    existing_project_id ist die effektive bestehende ID (project_id or linked_project_id).
    clear_project_link=True entfernt project_id und linked_project_id bewusst.
    Unverändertes project_id=null ohne clear_project_link lässt linked_project_id unangetastet.
    """
    payload.pop("clear_project_link", None)
    if clear_project_link:
        payload["project_id"] = None
        payload["linked_project_id"] = None
        return payload

    if "project_id" not in payload:
        return payload
    project_id = payload.get("project_id")
    if project_id is None:
        # Kein explizites Entfernen: Verknüpfung (auch nur linked_project_id) behalten
        payload.pop("linked_project_id", None)
        return payload
    if not isinstance(project_id, int) or project_id < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Ungültige Projekt-ID",
        )
    project = db.get(Project, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Projekt nicht gefunden oder inaktiv",
        )
    keeping_existing = existing_project_id is not None and project_id == existing_project_id
    if not keeping_existing and not project.active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Projekt nicht gefunden oder inaktiv",
        )
    program = db.get(Program, project.program_id)
    if not program:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Programm zum Projekt nicht gefunden",
        )
    customer = db.get(Customer, program.customer_id)
    payload["project_id"] = project.id
    payload["linked_project_id"] = project.id
    payload["kunde"] = customer.name if customer else ""
    payload["projekt"] = project.name
    return payload


def _baugruppe_to_read(db: Session, obj: Baugruppe) -> BaugruppeRead:
    calc = obj.ergebnis if isinstance(obj.ergebnis, dict) else {}
    sg_zw: dict[int, float] = {}
    kt_zw: dict[int, float] = {}
    vd_zw: dict[int, float] = {}
    for p in calc.get("einzelteile", []) or []:
        if isinstance(p, dict):
            sg_zw[p.get("id_ref", 0)] = p.get("zwischensumme", 0)
    for p in calc.get("kaufteile", []) or []:
        if isinstance(p, dict):
            kt_zw[p.get("id_ref", 0)] = p.get("zwischensumme", 0)
    for p in calc.get("veredelungen", []) or []:
        if isinstance(p, dict):
            vd_zw[p.get("veredelungsschritt_id", 0)] = p.get("zwischensumme", 0)

    sg_rows = db.scalars(
        select(BaugruppeSpritzgussZuordnung)
        .where(BaugruppeSpritzgussZuordnung.baugruppe_id == obj.id)
        .order_by(BaugruppeSpritzgussZuordnung.reihenfolge)
    ).all()
    kt_rows = db.scalars(
        select(BaugruppeKaufteilZuordnung)
        .where(BaugruppeKaufteilZuordnung.baugruppe_id == obj.id)
        .order_by(BaugruppeKaufteilZuordnung.reihenfolge)
    ).all()
    vd_rows = db.scalars(
        select(BaugruppeVeredelungZuordnung)
        .where(BaugruppeVeredelungZuordnung.baugruppe_id == obj.id)
        .order_by(BaugruppeVeredelungZuordnung.reihenfolge)
    ).all()

    investitionen = _load_investitionen(
        db,
        obj.id,
        [r.spritzguss_kalkulation_id for r in sg_rows],
    )

    base = BaugruppeRead.model_validate(obj)
    effective_project_id = _effective_project_id(obj)
    return base.model_copy(
        update={
            "project_id": effective_project_id,
            "customer_id": _resolve_customer_id_for_project(db, effective_project_id),
            "program_id": _resolve_program_id_for_project(db, effective_project_id),
            "spritzguss_zuordnungen": [
                SpritzgussZuordnungRead(
                    id=r.id,
                    baugruppe_id=r.baugruppe_id,
                    spritzguss_kalkulation_id=r.spritzguss_kalkulation_id,
                    menge=r.menge,
                    reihenfolge=r.reihenfolge,
                    snapshot_preis=r.snapshot_preis,
                    snapshot_bezeichnung=r.snapshot_bezeichnung,
                    snapshot_teilenummer=r.snapshot_teilenummer,
                    zwischensumme=sg_zw.get(r.spritzguss_kalkulation_id, 0),
                )
                for r in sg_rows
            ],
            "kaufteil_zuordnungen": [
                KaufteilZuordnungRead(
                    id=r.id,
                    baugruppe_id=r.baugruppe_id,
                    kaufteil_id=r.kaufteil_id,
                    menge=r.menge,
                    reihenfolge=r.reihenfolge,
                    snapshot_preis=r.snapshot_preis,
                    snapshot_bezeichnung=r.snapshot_bezeichnung,
                    snapshot_lieferant=r.snapshot_lieferant,
                    zwischensumme=kt_zw.get(r.kaufteil_id, 0),
                )
                for r in kt_rows
            ],
            "veredelung_zuordnungen": [
                VeredelungZuordnungRead(
                    id=r.id,
                    baugruppe_id=r.baugruppe_id,
                    veredelungsschritt_id=r.veredelungsschritt_id,
                    reihenfolge=r.reihenfolge,
                    mengenfaktor=r.mengenfaktor,
                    snapshot_kosten=r.snapshot_kosten,
                    snapshot_bezeichnung=r.snapshot_bezeichnung,
                    zwischensumme=vd_zw.get(r.veredelungsschritt_id, 0),
                )
                for r in vd_rows
            ],
            "investitionen": [
                InvestitionRead(
                    id=i.id,
                    bezeichnung=i.bezeichnung,
                    investment_type=i.investment_type,
                    amount=i.amount,
                    status=i.status,
                    quelle=i.quelle,
                )
                for i in investitionen
            ],
        }
    )


@router.post("/berechnen", response_model=BaugruppeCalcResponse)
def berechnen(
    body: BaugruppeCalcRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    return _build_calc_response(
        db,
        name=body.name,
        jahresstueckzahl=body.jahresstueckzahl,
        spritzguss_zuordnungen=body.spritzguss_zuordnungen,
        kaufteil_zuordnungen=body.kaufteil_zuordnungen,
        veredelung_zuordnungen=body.veredelung_zuordnungen,
        use_snapshots=False,
        werk_id=body.werk_id,
        project_id=body.project_id,
    )


@router.get("", response_model=list[BaugruppeListItem])
def list_baugruppen(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    aktiv: bool | None = Query(
        None,
        description="Filter: true=nur aktiv, false=nur archiviert, ohne Parameter=alle",
    ),
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    stmt = select(Baugruppe).order_by(Baugruppe.updated_at.desc())
    if aktiv is True:
        stmt = stmt.where(Baugruppe.aktiv.is_(True))
    elif aktiv is False:
        stmt = stmt.where(Baugruppe.aktiv.is_(False))
    rows = db.scalars(stmt.offset(skip).limit(limit)).all()
    result: list[BaugruppeListItem] = []
    for row in rows:
        preis = None
        if isinstance(row.ergebnis, dict):
            preis = row.ergebnis.get("baugruppenpreis_je_stueck")
        result.append(
            BaugruppeListItem(
                id=row.id,
                name=row.name,
                teilenummer=row.teilenummer,
                kunde=row.kunde,
                projekt=row.projekt,
                project_id=row.project_id or row.linked_project_id,
                jahresstueckzahl=row.jahresstueckzahl,
                status=row.status,
                baugruppenpreis_je_stueck=preis,
                updated_at=row.updated_at,
                aktiv=row.aktiv,
            )
        )
    return result


@router.get("/{item_id}", response_model=BaugruppeRead)
def get_baugruppe(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_viewer),
):
    obj = db.get(Baugruppe, item_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baugruppe nicht gefunden")
    return _baugruppe_to_read(db, obj)


@router.post("", response_model=BaugruppeRead, status_code=status.HTTP_201_CREATED)
def create_baugruppe(
    body: BaugruppeCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    payload = body.model_dump(
        exclude={"spritzguss_zuordnungen", "kaufteil_zuordnungen", "veredelung_zuordnungen"}
    )
    payload = _apply_project_to_baugruppe_payload(db, payload)
    project_id = payload.get("project_id")
    payload = _apply_jahresstueckzahl_from_project(
        db,
        payload,
        existing_project_id=None,
        existing_jahresstueckzahl=None,
        project_changed=project_id is not None,
        clear_project_link=False,
    )
    # Status → aktiv konsistent
    if payload.get("status") == "archiviert":
        payload["aktiv"] = False
    elif payload.get("status") == "aktiv":
        payload["aktiv"] = True
    obj = Baugruppe(**payload)
    db.add(obj)
    db.flush()
    sg_norm = _normalize_spritzguss_zuordnungen(body.spritzguss_zuordnungen)
    kt_norm = _normalize_kaufteil_zuordnungen(body.kaufteil_zuordnungen)
    _validate_zuordnungen_project_scope(db, project_id, sg_norm, kt_norm)
    _sync_spritzguss_zuordnungen(db, obj, sg_norm)
    _sync_kaufteil_zuordnungen(db, obj, kt_norm)
    _sync_veredelung_zuordnungen(db, obj, body.veredelung_zuordnungen)
    _apply_calculation(db, obj)
    db.commit()
    db.refresh(obj)
    return _baugruppe_to_read(db, obj)


@router.put("/{item_id}", response_model=BaugruppeRead)
def update_baugruppe(
    item_id: int,
    body: BaugruppeUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    obj = db.get(Baugruppe, item_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baugruppe nicht gefunden")

    updates = body.model_dump(exclude_unset=True)
    sg_z = updates.pop("spritzguss_zuordnungen", None)
    kt_z = updates.pop("kaufteil_zuordnungen", None)
    vd_z = updates.pop("veredelung_zuordnungen", None)
    clear_project_link = bool(updates.pop("clear_project_link", False))
    existing_pid = _effective_project_id(obj)
    updates = _apply_project_to_baugruppe_payload(
        db,
        updates,
        existing_project_id=existing_pid,
        clear_project_link=clear_project_link,
    )
    new_pid = updates.get("project_id", existing_pid if not clear_project_link else None)
    project_changed = clear_project_link or (
        "project_id" in body.model_dump(exclude_unset=True)
        and new_pid != existing_pid
    )
    updates = _apply_jahresstueckzahl_from_project(
        db,
        updates,
        existing_project_id=existing_pid,
        existing_jahresstueckzahl=obj.jahresstueckzahl,
        project_changed=project_changed,
        clear_project_link=clear_project_link,
    )

    # Bewusste Reaktivierung / Archivierung über Status
    if "status" in updates:
        if updates["status"] == "aktiv":
            updates["aktiv"] = True
        elif updates["status"] == "archiviert":
            updates["aktiv"] = False

    for field, value in updates.items():
        setattr(obj, field, value)

    effective_pid = _effective_project_id(obj)
    allow_sg: set[int] = {
        r.spritzguss_kalkulation_id
        for r in db.scalars(
            select(BaugruppeSpritzgussZuordnung).where(
                BaugruppeSpritzgussZuordnung.baugruppe_id == obj.id
            )
        ).all()
    }
    allow_kt: set[int] = {
        r.kaufteil_id
        for r in db.scalars(
            select(BaugruppeKaufteilZuordnung).where(
                BaugruppeKaufteilZuordnung.baugruppe_id == obj.id
            )
        ).all()
    }

    if sg_z is not None:
        sg_norm = _normalize_spritzguss_zuordnungen(sg_z)
        _validate_zuordnungen_project_scope(
            db,
            effective_pid,
            sg_norm,
            [],
            allow_inactive_spritzguss_ids=allow_sg,
        )
        _sync_spritzguss_zuordnungen(db, obj, sg_norm)
    if kt_z is not None:
        kt_norm = _normalize_kaufteil_zuordnungen(kt_z)
        _validate_zuordnungen_project_scope(
            db,
            effective_pid,
            [],
            kt_norm,
            allow_inactive_kaufteil_ids=allow_kt,
        )
        _sync_kaufteil_zuordnungen(db, obj, kt_norm)
    if vd_z is not None:
        _sync_veredelung_zuordnungen(db, obj, vd_z)

    _apply_calculation(db, obj)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return _baugruppe_to_read(db, obj)


@router.post("/{item_id}/archivieren", status_code=status.HTTP_204_NO_CONTENT)
def archivieren_baugruppe(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    """Weiches Archivieren – Datensatz und Positionen bleiben erhalten."""
    obj = db.get(Baugruppe, item_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baugruppe nicht gefunden")
    obj.aktiv = False
    obj.status = "archiviert"
    db.add(obj)
    db.commit()


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_baugruppe(
    item_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_kalkulator),
):
    """Hartes Löschen der Baugruppe inkl. eigener Positions-/Zuordnungsdaten.

    Blockiert mit HTTP 409, wenn andere Baugruppen diese als Unterbaugruppe
    (child_assembly_id) referenzieren – FK RESTRICT.
    Eigene assembly_positions und Legacy-Zuordnungen werden mitgelöscht
    (ORM cascade / FK CASCADE), damit keine verwaisten Positionen entstehen.
    """
    obj = db.get(Baugruppe, item_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baugruppe nicht gefunden")

    used_as_child = db.scalar(
        select(func.count())
        .select_from(AssemblyPosition)
        .where(AssemblyPosition.child_assembly_id == item_id)
    )
    if used_as_child:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Baugruppe kann nicht gelöscht werden, weil sie noch als Unterbaugruppe "
                f"in {used_as_child} Position(en) anderer Baugruppen verwendet wird. "
                "Bitte diese Verknüpfungen zuerst entfernen."
            ),
        )

    # Eigene Abhängigkeiten explizit entfernen (SQLite ohne FK-Enforcement + Klarheit)
    for pos in db.scalars(
        select(AssemblyPosition).where(AssemblyPosition.parent_assembly_id == item_id)
    ).all():
        db.delete(pos)
    for row in db.scalars(
        select(BaugruppeSpritzgussZuordnung).where(
            BaugruppeSpritzgussZuordnung.baugruppe_id == item_id
        )
    ).all():
        db.delete(row)
    for row in db.scalars(
        select(BaugruppeKaufteilZuordnung).where(
            BaugruppeKaufteilZuordnung.baugruppe_id == item_id
        )
    ).all():
        db.delete(row)
    for row in db.scalars(
        select(BaugruppeVeredelungZuordnung).where(
            BaugruppeVeredelungZuordnung.baugruppe_id == item_id
        )
    ).all():
        db.delete(row)

    db.delete(obj)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Baugruppe kann nicht gelöscht werden, weil noch abhängige Datensätze "
                "darauf verweisen. Bitte Verknüpfungen prüfen und entfernen."
            ),
        ) from exc

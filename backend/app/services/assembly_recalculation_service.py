"""Orchestrierung für Baugruppen-Neuberechnung (Phase C)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import Baugruppe
from app.models.kaufteil import Kaufteil
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.models.veredelungsschritt import Veredelungsschritt
from app.schemas.assembly_calculation import (
    AssemblyCalculationResultRead,
    AssemblyRecalculateRequest,
    AssemblyRecalculateResponse,
    CalculationWarning,
    PositionCalculationLineRead,
)
from app.schemas.assembly_structure import AssemblyPositionInput
from app.services.assembly_calculation import (
    AssemblyCalculationError,
    MarkupRates,
    PositionCalcInput,
    calculate_assembly,
)
from app.services.assembly_process_validation import collect_duplicate_process_warnings
from app.services.assembly_structure_service import (
    detect_cycle,
    effective_project_id,
    get_baugruppe_or_raise,
    load_positions,
    validate_project_scope,
    validate_referenced_entities_exist,
    validate_subassembly_rules,
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
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss
from app.services.veredelung_kalkulation import VeredelungInput, berechne_veredelung
from decimal import Decimal, ROUND_HALF_UP


def _money(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class AssemblyRecalculationError(Exception):
    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def _parse_ergebnis(raw: Any) -> dict | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _live_process_cost(schritt: Veredelungsschritt) -> float:
    return berechne_veredelung(
        VeredelungInput(
            taktzeit_s=schritt.taktzeit_s,
            anzahl_mitarbeiter=schritt.anzahl_mitarbeiter,
            lohnstundensatz=schritt.lohnstundensatz,
            maschinenstundensatz=schritt.maschinenstundensatz,
            verbrauchskosten_je_stueck=schritt.verbrauchskosten_je_stueck,
            ausschussquote_pct=schritt.ausschussquote_pct,
            fgk_pct=0,
            reihenfolge=schritt.reihenfolge,
        )
    ).kosten_inkl_ausschuss


def _load_spritzguss_calc_input(db: Session, part_calculation_id: int) -> SpritzgussInput:
    row = db.execute(
        text(
            """
            SELECT teilegewicht_netto_g, materialpreis_pro_kg, ausschussquote_pct, mgk_pct,
                   zykluszeit_s, maschinenstundensatz, kavitaeten, lohnstundensatz, fgk_pct,
                   werkzeugkosten_eur, werkzeug_abrechnungsart, amortisationsvolumen,
                   vvgk_pct, gewinn_pct, skonto_pct, material_nominierung
            FROM spritzguss_kalkulationen WHERE id = :id
            """
        ),
        {"id": part_calculation_id},
    ).first()
    if not row:
        raise AssemblyRecalculationError(
            f"Spritzguss-Kalkulation {part_calculation_id} nicht gefunden",
            status_code=404,
        )
    return SpritzgussInput(
        teilegewicht_netto_g=row[0],
        materialpreis_pro_kg=row[1],
        ausschussquote_pct=row[2],
        mgk_pct=row[3],
        zykluszeit_s=row[4],
        maschinenstundensatz=row[5],
        kavitaeten=row[6],
        lohnstundensatz=row[7],
        fgk_pct=row[8],
        werkzeugkosten_eur=row[9],
        werkzeug_abrechnungsart=row[10],  # type: ignore[arg-type]
        amortisationsvolumen=row[11],
        vvgk_pct=row[12],
        gewinn_pct=row[13],
        skonto_pct=row[14],
        material_nominierung=row[15],  # type: ignore[arg-type]
    )


def _load_part_meta(db: Session, part_calculation_id: int) -> tuple[str, str, float, float, float]:
    row = db.execute(
        text(
            "SELECT teilebezeichnung, teilenummer, vvgk_pct, gewinn_pct, skonto_pct "
            "FROM spritzguss_kalkulationen WHERE id = :id"
        ),
        {"id": part_calculation_id},
    ).first()
    if not row:
        raise AssemblyRecalculationError(
            f"Spritzguss-Kalkulation {part_calculation_id} nicht gefunden",
            status_code=404,
        )
    return row[0], row[1], row[2], row[3], row[4]


def _compute_part_live_values(
    db: Session, part_calculation_id: int
) -> tuple[float, float, str, str]:
    try:
        rates = load_central_markup_rates(db)
    except CentralMarkupRatesError as exc:
        raise AssemblyRecalculationError(str(exc)) from exc

    calc_input = _load_spritzguss_calc_input(db, part_calculation_id)
    try:
        mgk_pct = rates.mgk_pct_for_nominierung(
            calc_input.material_nominierung,
            kontext=f"Spritzguss-Materialeinsatz (Kalkulation {part_calculation_id})",
        )
    except CentralMarkupRatesError as exc:
        raise AssemblyRecalculationError(str(exc)) from exc

    # Zentrale Sätze überschreiben gespeicherte Prozentsätze
    calc_input = SpritzgussInput(
        teilegewicht_netto_g=calc_input.teilegewicht_netto_g,
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
    )
    name, part_number, *_legacy = _load_part_meta(db, part_calculation_id)

    spritzguss = berechne_spritzguss(calc_input)
    spritzguss_dict = spritzguss.to_dict()

    veredelung_eingaben: list[VeredelungSchrittEingabe] = []
    for zuordnung in db.scalars(
        select(SpritzgussVeredelungZuordnung)
        .where(SpritzgussVeredelungZuordnung.kalkulation_id == part_calculation_id)
        .order_by(SpritzgussVeredelungZuordnung.reihenfolge)
    ).all():
        schritt_row = db.execute(
            text(
                "SELECT bezeichnung, veredelungsart, taktzeit_s, anzahl_mitarbeiter, "
                "lohnstundensatz, maschinenstundensatz, verbrauchskosten_je_stueck, "
                "ausschussquote_pct, fgk_pct, reihenfolge "
                "FROM veredelungsschritte WHERE id = :id"
            ),
            {"id": zuordnung.veredelungsschritt_id},
        ).first()
        if not schritt_row:
            raise AssemblyRecalculationError(
                f"Veredelungsschritt {zuordnung.veredelungsschritt_id} nicht gefunden",
                status_code=404,
            )
        kosten_result = berechne_veredelung(
            VeredelungInput(
                taktzeit_s=schritt_row[2],
                anzahl_mitarbeiter=schritt_row[3],
                lohnstundensatz=schritt_row[4],
                maschinenstundensatz=schritt_row[5],
                verbrauchskosten_je_stueck=schritt_row[6],
                ausschussquote_pct=schritt_row[7],
                fgk_pct=0,
                reihenfolge=schritt_row[9],
            )
        )
        veredelung_eingaben.append(
            VeredelungSchrittEingabe(
                veredelungsschritt_id=zuordnung.veredelungsschritt_id,
                bezeichnung=schritt_row[0],
                veredelungsart=schritt_row[1],
                reihenfolge=zuordnung.reihenfolge,
                aktiv=zuordnung.aktiv,
                mengenfaktor=zuordnung.mengenfaktor,
                kosten_inkl_ausschuss=kosten_result.kosten_inkl_ausschuss,
                kosten_vor_ausschuss=kosten_result.kosten_vor_ausschuss,
                ausschussquote_pct=float(schritt_row[7]),
            )
        )

    try:
        gesamt = berechne_gesamt(
            spritzguss_dict,
            veredelung_eingaben,
            fgk_pct=rates.fgk_pct,
            vvgk_pct=rates.vvgk_pct,
            gewinn_pct=rates.gewinn_pct,
            skonto_pct=rates.skonto_pct,
        )
    except GesamtValidationError as exc:
        raise AssemblyRecalculationError(
            f"Herstellkosten für Einzelteil {part_calculation_id} konnten nicht ermittelt werden: {exc}"
        ) from exc

    return (
        float(gesamt.gesamte_herstellkosten),
        float(gesamt.endpreis_je_stueck),
        name,
        part_number,
    )


def load_global_markup_rates(db: Session) -> MarkupRates:
    try:
        rates = load_central_markup_rates(db)
    except CentralMarkupRatesError as exc:
        raise AssemblyRecalculationError(str(exc)) from exc
    return MarkupRates(
        vvgk_pct=rates.vvgk_pct,
        gewinn_pct=rates.gewinn_pct,
        skonto_pct=rates.skonto_pct,
        fgk_pct=rates.fgk_pct,
    )


def _validate_recalc_prerequisites(db: Session, baugruppe: Baugruppe) -> list[AssemblyPosition]:
    positions = load_positions(db, baugruppe.id)
    if not positions:
        raise AssemblyRecalculationError(
            "Keine Struktur – bitte zuerst assembly_positions anlegen",
            status_code=400,
        )
    if effective_project_id(baugruppe) is None:
        raise AssemblyRecalculationError("Projekt-Zuordnung fehlt", status_code=400)

    inputs = [
        AssemblyPositionInput(
            position_type=p.position_type,  # type: ignore[arg-type]
            sequence=p.sequence,
            quantity=p.quantity,
            quantity_factor=p.quantity_factor,
            price_basis=p.price_basis,  # type: ignore[arg-type]
            active=p.active,
            label=p.label,
            part_calculation_id=p.part_calculation_id,
            purchased_part_id=p.purchased_part_id,
            child_assembly_id=p.child_assembly_id,
            finishing_step_id=p.finishing_step_id,
        )
        for p in positions
    ]
    validate_referenced_entities_exist(db, inputs)
    validate_project_scope(db, baugruppe, inputs)
    validate_subassembly_rules(db, baugruppe, inputs)
    detect_cycle(db, baugruppe.id, inputs)
    return positions


def _validate_price_basis_for_calc(pos: AssemblyPosition, index: int) -> None:
    prefix = f"Position #{index}"
    if pos.price_basis == "SELF_COST":
        raise AssemblyRecalculationError(
            f"{prefix}: SELF_COST ist in Phase C noch nicht verfügbar"
        )
    if pos.position_type == "SUBASSEMBLY" and pos.price_basis != "COST":
        raise AssemblyRecalculationError(f"{prefix}: Unterbaugruppe erfordert price_basis=COST")


def _refresh_position_snapshot(
    db: Session,
    pos: AssemblyPosition,
    *,
    position_index: int,
) -> None:
    now = datetime.now(UTC)
    prefix = f"Position #{position_index}"

    if pos.position_type == "PART":
        if not pos.part_calculation_id:
            raise AssemblyRecalculationError(f"{prefix}: part_calculation_id fehlt")
        cost, price, name, part_number = _compute_part_live_values(db, pos.part_calculation_id)
        pos.cost_snapshot = cost
        pos.price_snapshot = price
        pos.name_snapshot = name
        pos.part_number_snapshot = part_number

    elif pos.position_type == "PURCHASED_PART":
        row = db.execute(
            text(
                "SELECT bezeichnung, lieferant, preis, nominierung FROM kaufteile WHERE id = :id"
            ),
            {"id": pos.purchased_part_id},
        ).first()
        if not row:
            raise AssemblyRecalculationError(f"{prefix}: Kaufteil nicht gefunden", status_code=404)
        try:
            rates = load_central_markup_rates(db)
            mgk_pct = rates.mgk_pct_for_nominierung(row[3])
        except CentralMarkupRatesError as exc:
            raise AssemblyRecalculationError(
                f"{prefix}: {exc}",
            ) from exc
        einkauf = float(row[2])
        pos.price_snapshot = _money(einkauf * (1 + mgk_pct / 100.0))
        pos.cost_snapshot = einkauf  # Roh-Einkaufspreis zur Transparenz
        pos.name_snapshot = row[0]
        pos.supplier_snapshot = row[1]

    elif pos.position_type == "PROCESS":
        row = db.execute(
            text(
                "SELECT bezeichnung, taktzeit_s, anzahl_mitarbeiter, lohnstundensatz, "
                "maschinenstundensatz, verbrauchskosten_je_stueck, ausschussquote_pct, "
                "fgk_pct, reihenfolge "
                "FROM veredelungsschritte WHERE id = :id"
            ),
            {"id": pos.finishing_step_id},
        ).first()
        if not row:
            raise AssemblyRecalculationError(
                f"{prefix}: Veredelungsschritt nicht gefunden", status_code=404
            )
        # FGK zentral in der Baugruppe – hier nur direkte Kosten
        vk = berechne_veredelung(
            VeredelungInput(
                taktzeit_s=row[1],
                anzahl_mitarbeiter=row[2],
                lohnstundensatz=row[3],
                maschinenstundensatz=row[4],
                verbrauchskosten_je_stueck=row[5],
                ausschussquote_pct=row[6],
                fgk_pct=0,
                reihenfolge=row[8],
            )
        )
        pos.cost_snapshot = vk.kosten_inkl_ausschuss
        pos.name_snapshot = row[0]

    elif pos.position_type == "SUBASSEMBLY":
        child = db.get(Baugruppe, pos.child_assembly_id)
        if not child:
            raise AssemblyRecalculationError(f"{prefix}: Unterbaugruppe nicht gefunden", status_code=404)
        pos.name_snapshot = child.name
        pos.part_number_snapshot = child.teilenummer

    pos.snapshots_captured_at = now


def _ensure_snapshots_present(db: Session, pos: AssemblyPosition, *, position_index: int) -> None:
    prefix = f"Position #{position_index}"
    if pos.position_type == "PART":
        if pos.price_basis == "COST" and (pos.cost_snapshot is None or pos.cost_snapshot <= 0):
            raise AssemblyRecalculationError(
                f"{prefix}: cost_snapshot fehlt – bitte mit refresh_snapshots=true neu berechnen"
            )
        if pos.price_basis == "SALES_PRICE" and (pos.price_snapshot is None or pos.price_snapshot <= 0):
            raise AssemblyRecalculationError(
                f"{prefix}: price_snapshot fehlt – bitte mit refresh_snapshots=true neu berechnen"
            )
    elif pos.position_type == "PURCHASED_PART":
        if pos.price_snapshot is None or pos.price_snapshot <= 0:
            raise AssemblyRecalculationError(
                f"{prefix}: price_snapshot fehlt – bitte mit refresh_snapshots=true neu berechnen"
            )
    elif pos.position_type == "PROCESS":
        if pos.cost_snapshot is None or pos.cost_snapshot <= 0:
            raise AssemblyRecalculationError(
                f"{prefix}: cost_snapshot fehlt – bitte mit refresh_snapshots=true neu berechnen"
            )


def _collect_child_ids(positions: list[AssemblyPosition]) -> list[int]:
    return [
        p.child_assembly_id
        for p in positions
        if p.position_type == "SUBASSEMBLY" and p.child_assembly_id is not None
    ]


def _child_recalc_order(db: Session, root_id: int) -> list[int]:
    order: list[int] = []
    visited: set[int] = set()

    def walk(assembly_id: int) -> None:
        if assembly_id in visited:
            return
        visited.add(assembly_id)
        for child_id in _collect_child_ids(load_positions(db, assembly_id)):
            walk(child_id)
        if assembly_id != root_id:
            order.append(assembly_id)

    for child_id in _collect_child_ids(load_positions(db, root_id)):
        walk(child_id)
    return order


def _build_calc_inputs(
    db: Session,
    positions: list[AssemblyPosition],
    child_herstellkosten: dict[int, float],
) -> list[PositionCalcInput]:
    inputs: list[PositionCalcInput] = []
    for pos in positions:
        child_hk = None
        if pos.position_type == "SUBASSEMBLY" and pos.child_assembly_id:
            child_hk = child_herstellkosten.get(pos.child_assembly_id)
        ausschussquote_pct = None
        cost_before_scrap = None
        if pos.position_type == "PROCESS" and pos.finishing_step_id:
            row = db.execute(
                text(
                    "SELECT taktzeit_s, anzahl_mitarbeiter, lohnstundensatz, "
                    "maschinenstundensatz, verbrauchskosten_je_stueck, ausschussquote_pct, "
                    "reihenfolge FROM veredelungsschritte WHERE id = :id"
                ),
                {"id": pos.finishing_step_id},
            ).first()
            if row:
                quote = float(row[5] or 0)
                ausschussquote_pct = quote
                if pos.cost_snapshot is not None and pos.cost_snapshot > 0:
                    # Vorhandener Snapshot: Vor-Kosten aus Snapshot ableiten
                    # (inkl. Eigenausschuss → vor = inkl × (1−q)), Quote aus Stammdaten
                    if quote > 0:
                        cost_before_scrap = float(pos.cost_snapshot) * (1.0 - quote / 100.0)
                    else:
                        cost_before_scrap = float(pos.cost_snapshot)
                else:
                    vk = berechne_veredelung(
                        VeredelungInput(
                            taktzeit_s=row[0],
                            anzahl_mitarbeiter=row[1],
                            lohnstundensatz=row[2],
                            maschinenstundensatz=row[3],
                            verbrauchskosten_je_stueck=row[4],
                            ausschussquote_pct=row[5],
                            fgk_pct=0,
                            reihenfolge=row[6],
                        )
                    )
                    cost_before_scrap = vk.kosten_vor_ausschuss
        inputs.append(
            PositionCalcInput(
                position_id=pos.id,
                position_type=pos.position_type,
                sequence=pos.sequence,
                quantity=pos.quantity,
                quantity_factor=pos.quantity_factor,
                price_basis=pos.price_basis,
                active=pos.active,
                label=pos.label,
                name_snapshot=pos.name_snapshot or "",
                cost_snapshot=pos.cost_snapshot,
                price_snapshot=pos.price_snapshot,
                child_herstellkosten=child_hk,
                ausschussquote_pct=ausschussquote_pct,
                cost_before_scrap=cost_before_scrap,
            )
        )
    return inputs


def _result_to_read(result) -> AssemblyCalculationResultRead:
    return AssemblyCalculationResultRead(
        herstellkosten=result.herstellkosten,
        vvgk=result.vvgk,
        selbstkosten=result.selbstkosten,
        gewinn=result.gewinn,
        nettoverkaufspreis=result.nettoverkaufspreis,
        skonto=result.skonto,
        endpreis_je_stueck=result.endpreis_je_stueck,
        markup_applied=result.markup_applied,
    )


def _persist_calculation(
    baugruppe: Baugruppe,
    result,
    *,
    refresh_snapshots: bool,
) -> None:
    payload = {
        "herstellkosten": result.herstellkosten,
        "fgk_basis": getattr(result, "fgk_basis", None),
        "fertigungsgemeinkosten": getattr(result, "fertigungsgemeinkosten", None),
        "vvgk": result.vvgk,
        "selbstkosten": result.selbstkosten,
        "gewinn": result.gewinn,
        "nettoverkaufspreis": result.nettoverkaufspreis,
        "skonto": result.skonto,
        "endpreis_je_stueck": result.endpreis_je_stueck,
        "markup_applied": result.markup_applied,
        "applied_fgk_pct": getattr(result, "applied_fgk_pct", None),
        "applied_vvgk_pct": getattr(result, "applied_vvgk_pct", None),
        "applied_gewinn_pct": getattr(result, "applied_gewinn_pct", None),
        "applied_skonto_pct": getattr(result, "applied_skonto_pct", None),
        "positions": [
            {
                "position_id": line.position_id,
                "position_type": line.position_type,
                "sequence": line.sequence,
                "label": line.label,
                "name_snapshot": line.name_snapshot,
                "einzelpreis": line.einzelpreis,
                "quantity": line.quantity,
                "quantity_factor": line.quantity_factor,
                "zwischensumme": line.zwischensumme,
            }
            for line in result.position_lines
        ],
        "warnings": [w.model_dump() for w in result.warnings],
        "process_yield_details": [
            {
                "position_id": d.position_id,
                "label": d.label,
                "name_snapshot": d.name_snapshot,
                "ausschussquote_pct": d.ausschussquote_pct,
                "vorprodukt_eingang": d.vorprodukt_eingang,
                "process_kosten_vor_ausschuss": d.process_kosten_vor_ausschuss,
                "ausschuss_zuschlag": d.ausschuss_zuschlag,
                "kosten_nach_ausbeute": d.kosten_nach_ausbeute,
            }
            for d in (result.process_yield_details or [])
        ],
    }
    baugruppe.ergebnis = payload
    if refresh_snapshots:
        baugruppe.snapshots_captured_at = datetime.now(UTC)
    if baugruppe.assembly_type == "TOP_LEVEL":
        baugruppe.pricing_status = "CALCULATED"
    else:
        baugruppe.pricing_status = "NOT_APPLICABLE"


def _recalculate_single(
    db: Session,
    baugruppe_id: int,
    request: AssemblyRecalculateRequest,
    *,
    child_herstellkosten: dict[int, float],
    markup_rates: MarkupRates | None,
    recalculated_ids: list[int],
    positions_preloaded: list[AssemblyPosition] | None = None,
) -> tuple[AssemblyCalculationResultRead, list[PositionCalculationLineRead], list[CalculationWarning], float]:
    baugruppe = get_baugruppe_or_raise(db, baugruppe_id)
    positions = positions_preloaded or _validate_recalc_prerequisites(db, baugruppe)
    if markup_rates is None:
        markup_rates = load_global_markup_rates(db)

    for index, pos in enumerate(sorted(positions, key=lambda p: p.sequence), start=1):
        _validate_price_basis_for_calc(pos, index)

    process_warnings = collect_duplicate_process_warnings(db, baugruppe.id, positions)

    if request.refresh_snapshots:
        for index, pos in enumerate(sorted(positions, key=lambda p: p.sequence), start=1):
            _refresh_position_snapshot(db, pos, position_index=index)
    else:
        for index, pos in enumerate(sorted(positions, key=lambda p: p.sequence), start=1):
            _ensure_snapshots_present(db, pos, position_index=index)

    calc_inputs = _build_calc_inputs(db, positions, child_herstellkosten)
    try:
        result = calculate_assembly(
            assembly_type=baugruppe.assembly_type,
            positions=calc_inputs,
            markup_rates=markup_rates,
            extra_warnings=process_warnings,
        )
    except AssemblyCalculationError as exc:
        raise AssemblyRecalculationError(str(exc)) from exc

    if not request.validate_only:
        _persist_calculation(baugruppe, result, refresh_snapshots=request.refresh_snapshots)
        recalculated_ids.append(baugruppe.id)

    position_reads = [
        PositionCalculationLineRead(
            position_id=line.position_id,
            position_type=line.position_type,
            sequence=line.sequence,
            label=line.label,
            name_snapshot=line.name_snapshot,
            einzelpreis=line.einzelpreis,
            quantity=line.quantity,
            quantity_factor=line.quantity_factor,
            zwischensumme=line.zwischensumme,
        )
        for line in result.position_lines
    ]
    return _result_to_read(result), position_reads, result.warnings, result.herstellkosten


def recalculate_assembly_tree(
    db: Session,
    root_id: int,
    request: AssemblyRecalculateRequest,
) -> AssemblyRecalculateResponse:
    root = get_baugruppe_or_raise(db, root_id)
    # Zuschlagssätze erst nach Struktur-/Basis-Validierung laden (klarere Fehlerreihenfolge)
    markup_rates: MarkupRates | None = None
    child_herstellkosten: dict[int, float] = {}
    recalculated_ids: list[int] = []

    if request.include_descendants:
        for child_id in _child_recalc_order(db, root_id):
            if not load_positions(db, child_id):
                continue
            if markup_rates is None:
                markup_rates = load_global_markup_rates(db)
            _, _, _, hk = _recalculate_single(
                db,
                child_id,
                request,
                child_herstellkosten=child_herstellkosten,
                markup_rates=markup_rates,
                recalculated_ids=recalculated_ids,
            )
            child_herstellkosten[child_id] = hk

    # Root: Voraussetzungen prüfen; Markups erst danach laden
    positions = _validate_recalc_prerequisites(db, root)
    for index, pos in enumerate(sorted(positions, key=lambda p: p.sequence), start=1):
        _validate_price_basis_for_calc(pos, index)
    if markup_rates is None:
        markup_rates = load_global_markup_rates(db)

    calc_read, positions_read, warnings, _ = _recalculate_single(
        db,
        root_id,
        request,
        child_herstellkosten=child_herstellkosten,
        markup_rates=markup_rates,
        recalculated_ids=recalculated_ids,
        positions_preloaded=positions,
    )

    if not request.validate_only:
        db.commit()
        db.refresh(root)
    else:
        db.rollback()

    pricing_status = "CALCULATED" if root.assembly_type == "TOP_LEVEL" else "NOT_APPLICABLE"
    if request.validate_only:
        pricing_status = root.pricing_status

    return AssemblyRecalculateResponse(
        assembly_id=root.id,
        assembly_type=root.assembly_type,  # type: ignore[arg-type]
        structure_version=root.structure_version,
        pricing_status=pricing_status,
        snapshots_captured_at=root.snapshots_captured_at,
        calculation=calc_read,
        positions=positions_read,
        warnings=warnings,
        recalculated_assembly_ids=recalculated_ids,
    )


def _safe_timestamp(db: Session, sql: str, params: dict[str, Any]) -> datetime | None:
    try:
        value = db.execute(text(sql), params).scalar()
    except Exception:
        return None
    return _normalize_datetime(value)


def _normalize_datetime(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, str):
        cleaned = value.replace("Z", "+00:00")
        for parser in (
            lambda s: datetime.fromisoformat(s),
            lambda s: datetime.fromisoformat(s.replace(" ", "T")),
        ):
            try:
                return parser(cleaned)
            except ValueError:
                continue
        return None
    if isinstance(value, datetime):
        return value
    return None


def is_position_snapshot_stale(db: Session, pos: AssemblyPosition) -> bool:
    if pos.snapshots_captured_at is None:
        return True

    captured = pos.snapshots_captured_at
    if captured.tzinfo is None:
        captured = captured.replace(tzinfo=UTC)

    def _is_newer(updated_at: datetime | str | None) -> bool:
        normalized = _normalize_datetime(updated_at)
        if normalized is None:
            return False
        if normalized.tzinfo is None:
            normalized = normalized.replace(tzinfo=UTC)
        return normalized > captured

    if pos.position_type == "PART" and pos.part_calculation_id:
        updated = _safe_timestamp(
            db,
            "SELECT updated_at FROM spritzguss_kalkulationen WHERE id = :id",
            {"id": pos.part_calculation_id},
        )
        if _is_newer(updated):
            return True
        rows = []
        try:
            rows = db.execute(
                text(
                    "SELECT updated_at FROM spritzguss_veredelung_zuordnungen "
                    "WHERE kalkulation_id = :id"
                ),
                {"id": pos.part_calculation_id},
            ).all()
        except Exception:
            rows = []
        for (row_updated,) in rows:
            if _is_newer(row_updated):
                return True
    elif pos.position_type == "PURCHASED_PART" and pos.purchased_part_id:
        updated = _safe_timestamp(
            db,
            "SELECT updated_at FROM kaufteile WHERE id = :id",
            {"id": pos.purchased_part_id},
        )
        if _is_newer(updated):
            return True
    elif pos.position_type == "PROCESS" and pos.finishing_step_id:
        updated = _safe_timestamp(
            db,
            "SELECT updated_at FROM veredelungsschritte WHERE id = :id",
            {"id": pos.finishing_step_id},
        )
        if _is_newer(updated):
            return True
    elif pos.position_type == "SUBASSEMBLY" and pos.child_assembly_id:
        child = db.get(Baugruppe, pos.child_assembly_id)
        if child and (_is_newer(child.updated_at) or child.pricing_status == "STALE"):
            return True
    return False


def calculation_from_baugruppe(baugruppe: Baugruppe) -> AssemblyCalculationResultRead | None:
    data = _parse_ergebnis(baugruppe.ergebnis)
    if not data or "herstellkosten" not in data:
        return None
    return AssemblyCalculationResultRead(
        herstellkosten=float(data.get("herstellkosten", 0)),
        vvgk=data.get("vvgk"),
        selbstkosten=data.get("selbstkosten"),
        gewinn=data.get("gewinn"),
        nettoverkaufspreis=data.get("nettoverkaufspreis"),
        skonto=data.get("skonto"),
        endpreis_je_stueck=data.get("endpreis_je_stueck"),
        markup_applied=bool(data.get("markup_applied", False)),
    )


def warnings_from_baugruppe(baugruppe: Baugruppe) -> list[CalculationWarning]:
    data = _parse_ergebnis(baugruppe.ergebnis)
    if not data:
        return []
    raw = data.get("warnings") or []
    return [CalculationWarning.model_validate(item) for item in raw if isinstance(item, dict)]

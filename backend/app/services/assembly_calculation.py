"""Reine rekursive Baugruppen-Kalkulation aus Snapshots (Phase C)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.assembly_calculation import CalculationWarning


from app.services.process_yield import apply_process_yield


class AssemblyCalculationError(ValueError):
    """Fachlicher Kalkulationsfehler."""


def _d(value: float | int) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MarkupRates:
    """TOP_LEVEL-Zuschläge.

    FGK wird nur auf PROCESS-Positionen (direkte Veredelung) addiert –
    PART-/SUBASSEMBLY-Herstellkosten enthalten FGK bereits.
    Baugruppe TOP_LEVEL: keine zusätzliche VVGK/SG&A (bereits in Positions-Snapshots),
    Gewinn und Skonto einmal auf die so ermittelten Herstellkosten.
    """

    vvgk_pct: float | None = None
    gewinn_pct: float | None = None
    skonto_pct: float | None = None
    fgk_pct: float | None = None


@dataclass(frozen=True)
class PositionCalcInput:
    position_id: int | None
    position_type: str
    sequence: int
    quantity: float
    quantity_factor: float
    price_basis: str | None
    active: bool
    label: str | None
    name_snapshot: str
    cost_snapshot: float | None
    price_snapshot: float | None
    child_herstellkosten: float | None = None
    # PROCESS: Ausbeutekette (optional – ohne Werte: Legacy-Additiv)
    ausschussquote_pct: float | None = None
    cost_before_scrap: float | None = None


@dataclass(frozen=True)
class ProcessYieldDetail:
    position_id: int | None
    label: str | None
    name_snapshot: str
    ausschussquote_pct: float
    vorprodukt_eingang: float
    process_kosten_vor_ausschuss: float
    ausschuss_zuschlag: float
    kosten_nach_ausbeute: float


@dataclass(frozen=True)
class PositionCalculationLine:
    position_id: int | None
    position_type: str
    sequence: int
    label: str | None
    name_snapshot: str
    einzelpreis: float
    quantity: float
    quantity_factor: float
    zwischensumme: float


@dataclass(frozen=True)
class AssemblyCalculationResult:
    assembly_type: str
    herstellkosten: float
    vvgk: float | None
    selbstkosten: float | None
    gewinn: float | None
    nettoverkaufspreis: float | None
    skonto: float | None
    endpreis_je_stueck: float | None
    markup_applied: bool
    position_lines: list[PositionCalculationLine]
    warnings: list[CalculationWarning]
    fertigungsgemeinkosten: float | None = None
    fgk_basis: float | None = None
    applied_fgk_pct: float | None = None
    applied_vvgk_pct: float | None = None
    applied_gewinn_pct: float | None = None
    applied_skonto_pct: float | None = None
    process_yield_details: list[ProcessYieldDetail] | None = None


def _pct_rate(pct: float) -> Decimal:
    return _d(pct) / Decimal("100")


def _require_positive_snapshot(value: float | None, *, label: str, position_index: int) -> Decimal:
    if value is None or value <= 0:
        raise AssemblyCalculationError(
            f"Position #{position_index}: {label} fehlt oder ist ungültig"
        )
    return _d(value)


def calculate_position_line(
    position: PositionCalcInput,
    *,
    position_index: int,
) -> tuple[PositionCalculationLine, list[CalculationWarning]]:
    warnings: list[CalculationWarning] = []

    if not position.active:
        raise AssemblyCalculationError(f"Position #{position_index}: inaktive Position übersprungen")

    if position.position_type == "PART":
        if position.price_basis == "SELF_COST":
            raise AssemblyCalculationError(
                f"Position #{position_index}: SELF_COST ist in Phase C noch nicht verfügbar"
            )
        if position.price_basis == "COST":
            unit = _require_positive_snapshot(
                position.cost_snapshot,
                label="cost_snapshot",
                position_index=position_index,
            )
        elif position.price_basis == "SALES_PRICE":
            unit = _require_positive_snapshot(
                position.price_snapshot,
                label="price_snapshot",
                position_index=position_index,
            )
            warnings.append(
                CalculationWarning(
                    code="DOUBLE_MARKUP_RISK",
                    message=(
                        f"Position #{position_index}: SALES_PRICE kann zu Doppelzuschlägen führen"
                    ),
                    position_id=position.position_id,
                )
            )
        else:
            raise AssemblyCalculationError(
                f"Position #{position_index}: unbekanntes price_basis '{position.price_basis}'"
            )
        zwischensumme = _money(unit * _d(position.quantity))
        einzelpreis = float(unit)

    elif position.position_type == "PURCHASED_PART":
        # price_snapshot enthält bereits Einkaufspreis inkl. MGK (beim Refresh)
        unit = _require_positive_snapshot(
            position.price_snapshot,
            label="price_snapshot",
            position_index=position_index,
        )
        zwischensumme = _money(unit * _d(position.quantity))
        einzelpreis = float(unit)

    elif position.position_type == "PROCESS":
        unit = _require_positive_snapshot(
            position.cost_snapshot,
            label="cost_snapshot",
            position_index=position_index,
        )
        zwischensumme = _money(unit * _d(position.quantity_factor))
        einzelpreis = float(unit)

    elif position.position_type == "SUBASSEMBLY":
        if position.price_basis != "COST":
            raise AssemblyCalculationError(
                f"Position #{position_index}: Unterbaugruppe erfordert price_basis=COST"
            )
        if position.child_herstellkosten is None or position.child_herstellkosten <= 0:
            raise AssemblyCalculationError(
                f"Position #{position_index}: Herstellkosten der Unterbaugruppe fehlen"
            )
        unit = _d(position.child_herstellkosten)
        zwischensumme = _money(unit * _d(position.quantity))
        einzelpreis = float(unit)

    else:
        raise AssemblyCalculationError(
            f"Position #{position_index}: unbekannter position_type '{position.position_type}'"
        )

    line = PositionCalculationLine(
        position_id=position.position_id,
        position_type=position.position_type,
        sequence=position.sequence,
        label=position.label,
        name_snapshot=position.name_snapshot,
        einzelpreis=einzelpreis,
        quantity=position.quantity,
        quantity_factor=position.quantity_factor,
        zwischensumme=float(zwischensumme),
    )
    return line, warnings


def _process_direct_cost(
    position: PositionCalcInput,
    *,
    position_index: int,
) -> Decimal:
    quote = float(position.ausschussquote_pct or 0)
    if position.cost_before_scrap is not None:
        vor_unit = _d(position.cost_before_scrap)
    elif position.cost_snapshot is not None and quote > 0:
        vor_unit = _d(position.cost_snapshot) * (Decimal("1") - _d(quote) / Decimal("100"))
    else:
        vor_unit = _require_positive_snapshot(
            position.cost_snapshot,
            label="cost_snapshot",
            position_index=position_index,
        )
    return vor_unit * _d(position.quantity_factor)


def apply_top_level_markups(
    herstellkosten: Decimal,
    rates: MarkupRates,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, list[CalculationWarning]]:
    missing: list[str] = []
    if rates.gewinn_pct is None:
        missing.append("Gewinn")
    if rates.skonto_pct is None:
        missing.append("Skonto")
    if missing:
        raise AssemblyCalculationError(f"Fehlende Zuschlagssätze: {', '.join(missing)}")

    gewinn_pct = rates.gewinn_pct
    skonto_pct = rates.skonto_pct
    assert gewinn_pct is not None and skonto_pct is not None

    # Keine Baugruppen-VVGK: SG&A liegt bereits in Einzelteil-/Kaufteil-Snapshots.
    vvgk = Decimal("0")
    selbstkosten = herstellkosten
    gewinn = herstellkosten * _pct_rate(gewinn_pct)
    nettoverkaufspreis = herstellkosten + gewinn
    skonto = nettoverkaufspreis * _pct_rate(skonto_pct)
    endpreis = nettoverkaufspreis + skonto
    return vvgk, selbstkosten, gewinn, nettoverkaufspreis, skonto, endpreis, []


def calculate_assembly(
    *,
    assembly_type: str,
    positions: list[PositionCalcInput],
    markup_rates: MarkupRates | None = None,
    extra_warnings: list[CalculationWarning] | None = None,
) -> AssemblyCalculationResult:
    active_positions = sorted(
        [p for p in positions if p.active],
        key=lambda p: p.sequence,
    )
    if not active_positions:
        raise AssemblyCalculationError("Keine aktiven Positionen für die Kalkulation")

    rates = markup_rates or MarkupRates()
    warnings: list[CalculationWarning] = list(extra_warnings or [])

    if assembly_type == "TOP_LEVEL":
        return _calculate_top_level(active_positions, rates, warnings)

    return _calculate_subassembly(active_positions, assembly_type, rates, warnings)


def _calculate_subassembly(
    active_positions: list[PositionCalcInput],
    assembly_type: str,
    rates: MarkupRates,
    warnings: list[CalculationWarning],
) -> AssemblyCalculationResult:
    lines: list[PositionCalculationLine] = []
    yield_details: list[ProcessYieldDetail] = []
    running = Decimal("0")
    process_direct_sum = Decimal("0")

    for index, position in enumerate(active_positions, start=1):
        if position.position_type == "PROCESS":
            quote = float(position.ausschussquote_pct or 0)
            vor = _money(_process_direct_cost(position, position_index=index))
            vorprodukt = running
            try:
                output, surcharge, _yf = apply_process_yield(running, vor, quote)
            except ValueError as exc:
                raise AssemblyCalculationError(str(exc)) from exc
            beitrag = _money(output - running)
            running = output
            process_direct_sum += vor
            lines.append(
                PositionCalculationLine(
                    position_id=position.position_id,
                    position_type=position.position_type,
                    sequence=position.sequence,
                    label=position.label,
                    name_snapshot=position.name_snapshot,
                    einzelpreis=float(vor / _d(position.quantity_factor)),
                    quantity=position.quantity,
                    quantity_factor=position.quantity_factor,
                    zwischensumme=float(beitrag),
                )
            )
            yield_details.append(
                ProcessYieldDetail(
                    position_id=position.position_id,
                    label=position.label,
                    name_snapshot=position.name_snapshot,
                    ausschussquote_pct=quote,
                    vorprodukt_eingang=float(vorprodukt),
                    process_kosten_vor_ausschuss=float(vor),
                    ausschuss_zuschlag=float(surcharge),
                    kosten_nach_ausbeute=float(output),
                )
            )
            continue

        line, line_warnings = calculate_position_line(position, position_index=index)
        lines.append(line)
        warnings.extend(line_warnings)
        running = _money(running + _d(line.zwischensumme))

    fgk_basis = _money(process_direct_sum)
    fertigungsgemeinkosten = Decimal("0")
    if assembly_type == "SUBASSEMBLY" and process_direct_sum > 0:
        if rates.fgk_pct is None:
            raise AssemblyCalculationError("Fehlende Zuschlagssätze: FGK")
        fertigungsgemeinkosten = _money(fgk_basis * _pct_rate(rates.fgk_pct))

    herstellkosten = _money(running + fertigungsgemeinkosten)

    if assembly_type != "SUBASSEMBLY":
        raise AssemblyCalculationError(f"Unbekannter assembly_type '{assembly_type}'")

    return AssemblyCalculationResult(
        assembly_type=assembly_type,
        herstellkosten=float(herstellkosten),
        vvgk=None,
        selbstkosten=None,
        gewinn=None,
        nettoverkaufspreis=None,
        skonto=None,
        endpreis_je_stueck=None,
        markup_applied=False,
        position_lines=lines,
        warnings=warnings,
        fertigungsgemeinkosten=float(fertigungsgemeinkosten),
        fgk_basis=float(fgk_basis),
        applied_fgk_pct=float(rates.fgk_pct) if rates.fgk_pct is not None else None,
        process_yield_details=yield_details,
    )


def _position_vorprodukt_beitrag(position: PositionCalcInput, *, position_index: int) -> Decimal:
    if position.position_type == "PART":
        if position.price_basis == "COST":
            unit = _require_positive_snapshot(
                position.cost_snapshot,
                label="cost_snapshot",
                position_index=position_index,
            )
        elif position.price_basis == "SALES_PRICE":
            unit = _require_positive_snapshot(
                position.price_snapshot,
                label="price_snapshot",
                position_index=position_index,
            )
        else:
            raise AssemblyCalculationError(
                f"Position #{position_index}: unbekanntes price_basis '{position.price_basis}'"
            )
        return unit * _d(position.quantity)
    if position.position_type == "PURCHASED_PART":
        unit = _require_positive_snapshot(
            position.price_snapshot,
            label="price_snapshot",
            position_index=position_index,
        )
        return unit * _d(position.quantity)
    if position.position_type == "SUBASSEMBLY":
        if position.child_herstellkosten is None or position.child_herstellkosten <= 0:
            raise AssemblyCalculationError(
                f"Position #{position_index}: Herstellkosten der Unterbaugruppe fehlen"
            )
        return _d(position.child_herstellkosten) * _d(position.quantity)
    raise AssemblyCalculationError(
        f"Position #{position_index}: unerwarteter position_type '{position.position_type}'"
    )


def _calculate_top_level(
    active_positions: list[PositionCalcInput],
    rates: MarkupRates,
    warnings: list[CalculationWarning],
) -> AssemblyCalculationResult:
    if rates.fgk_pct is None:
        raise AssemblyCalculationError("Fehlende Zuschlagssätze: FGK")

    lines: list[PositionCalculationLine] = []
    yield_details: list[ProcessYieldDetail] = []
    vorprodukt = Decimal("0")
    process_steps: list[tuple[PositionCalcInput, int, Decimal, Decimal]] = []
    process_direct_sum = Decimal("0")

    for index, position in enumerate(active_positions, start=1):
        if position.position_type == "PROCESS":
            quote = float(position.ausschussquote_pct or 0)
            vor = _process_direct_cost(position, position_index=index)
            vor_unit = vor / _d(position.quantity_factor)
            process_steps.append((position, index, vor, vor_unit))
            process_direct_sum += vor
            continue

        line, line_warnings = calculate_position_line(position, position_index=index)
        lines.append(line)
        warnings.extend(line_warnings)
        vorprodukt += _position_vorprodukt_beitrag(position, position_index=index)

    fgk_basis = process_direct_sum
    fertigungsgemeinkosten = fgk_basis * _pct_rate(rates.fgk_pct)
    running = vorprodukt + fertigungsgemeinkosten

    for position, index, vor, vor_unit in process_steps:
        quote = float(position.ausschussquote_pct or 0)
        vorprodukt_eingang = running
        try:
            output, surcharge, _yf = apply_process_yield(
                running,
                vor,
                quote,
                quantize=False,
            )
        except ValueError as exc:
            raise AssemblyCalculationError(str(exc)) from exc
        beitrag = output - running
        running = output
        lines.append(
            PositionCalculationLine(
                position_id=position.position_id,
                position_type=position.position_type,
                sequence=position.sequence,
                label=position.label,
                name_snapshot=position.name_snapshot,
                einzelpreis=float(vor_unit),
                quantity=position.quantity,
                quantity_factor=position.quantity_factor,
                zwischensumme=float(beitrag),
            )
        )
        yield_details.append(
            ProcessYieldDetail(
                position_id=position.position_id,
                label=position.label,
                name_snapshot=position.name_snapshot,
                ausschussquote_pct=quote,
                vorprodukt_eingang=float(vorprodukt_eingang),
                process_kosten_vor_ausschuss=float(vor),
                ausschuss_zuschlag=float(surcharge),
                kosten_nach_ausbeute=float(output),
            )
        )

    lines.sort(key=lambda line: line.sequence)
    herstellkosten = running

    vvgk, selbstkosten, gewinn, netto, skonto, endpreis, markup_warnings = apply_top_level_markups(
        herstellkosten, rates
    )
    warnings.extend(markup_warnings)

    return AssemblyCalculationResult(
        assembly_type="TOP_LEVEL",
        herstellkosten=float(herstellkosten),
        vvgk=float(vvgk),
        selbstkosten=float(selbstkosten),
        gewinn=float(gewinn),
        nettoverkaufspreis=float(netto),
        skonto=float(skonto),
        endpreis_je_stueck=float(endpreis),
        markup_applied=True,
        position_lines=lines,
        warnings=warnings,
        fertigungsgemeinkosten=float(fertigungsgemeinkosten),
        fgk_basis=float(fgk_basis),
        applied_fgk_pct=float(rates.fgk_pct),
        applied_vvgk_pct=0.0,
        applied_gewinn_pct=float(rates.gewinn_pct) if rates.gewinn_pct is not None else None,
        applied_skonto_pct=float(rates.skonto_pct) if rates.skonto_pct is not None else None,
        process_yield_details=yield_details,
    )

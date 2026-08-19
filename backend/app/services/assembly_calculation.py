"""Reine rekursive Baugruppen-Kalkulation aus Snapshots (Phase C)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from app.schemas.assembly_calculation import CalculationWarning


class AssemblyCalculationError(ValueError):
    """Fachlicher Kalkulationsfehler."""


def _d(value: float | int) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class MarkupRates:
    vvgk_pct: float | None = None
    gewinn_pct: float | None = None
    skonto_pct: float | None = None


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


def apply_top_level_markups(
    herstellkosten: Decimal,
    rates: MarkupRates,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal, Decimal, list[CalculationWarning]]:
    missing: list[str] = []
    if rates.vvgk_pct is None:
        missing.append("VVGK")
    if rates.gewinn_pct is None:
        missing.append("Gewinn")
    if rates.skonto_pct is None:
        missing.append("Skonto")
    if missing:
        raise AssemblyCalculationError(f"Fehlende Zuschlagssätze: {', '.join(missing)}")

    vvgk_pct = rates.vvgk_pct
    gewinn_pct = rates.gewinn_pct
    skonto_pct = rates.skonto_pct
    assert vvgk_pct is not None and gewinn_pct is not None and skonto_pct is not None

    vvgk = _money(herstellkosten * _pct_rate(vvgk_pct))
    selbstkosten = _money(herstellkosten + vvgk)
    gewinn = _money(selbstkosten * _pct_rate(gewinn_pct))
    nettoverkaufspreis = _money(selbstkosten + gewinn)
    skonto = _money(nettoverkaufspreis * _pct_rate(skonto_pct))
    endpreis = _money(nettoverkaufspreis + skonto)
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

    lines: list[PositionCalculationLine] = []
    warnings: list[CalculationWarning] = list(extra_warnings or [])
    herstellkosten = Decimal("0")

    for index, position in enumerate(active_positions, start=1):
        line, line_warnings = calculate_position_line(position, position_index=index)
        lines.append(line)
        warnings.extend(line_warnings)
        herstellkosten += _d(line.zwischensumme)

    herstellkosten = _money(herstellkosten)

    if assembly_type == "SUBASSEMBLY":
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
        )

    if assembly_type != "TOP_LEVEL":
        raise AssemblyCalculationError(f"Unbekannter assembly_type '{assembly_type}'")

    rates = markup_rates or MarkupRates()
    vvgk, selbstkosten, gewinn, netto, skonto, endpreis, markup_warnings = apply_top_level_markups(
        herstellkosten, rates
    )
    warnings.extend(markup_warnings)

    return AssemblyCalculationResult(
        assembly_type=assembly_type,
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
    )

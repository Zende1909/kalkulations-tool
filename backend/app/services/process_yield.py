"""Ausbeute-/Ausschusskaskade für Prozessschritte.

Fachmodell (Ausbeutekette, kein Doppelzuschlag innerhalb eines Schritts)
----------------------------------------------------------------------
Pro Prozessschritt genau einmal:

    Ausgang = (Vorproduktkosten + Prozesskosten_vor_Ausschuss) / (1 − Ausschussquote)

- Materialausschuss bleibt lokal am Material (Spritzguss).
- Kaschier-/ASSY-Ausschuss greift auf bereits hergestellte Vorprodukte zu.
- FGK-Basis bleibt: Maschinenkosten + Fertigungslohn + direkte Prozesskosten
  *vor* Ausschuss (kein erneutes Aufblasen der FGK-Basis durch denselben Ausschuss).
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def _d(value: float | int | Decimal | str) -> Decimal:
    return Decimal(str(value))


def _money(value: Decimal, places: str = "0.01") -> Decimal:
    return value.quantize(Decimal(places), rounding=ROUND_HALF_UP)


def apply_process_yield(
    upstream_cost: Decimal,
    process_cost_before_scrap: Decimal,
    ausschussquote_pct: float,
) -> tuple[Decimal, Decimal, Decimal]:
    """Wendet den Prozessausschuss einmal auf Vorprodukt + Prozesskosten an.

    Returns:
        (output_cost, scrap_surcharge, yield_factor)
        scrap_surcharge = output − upstream − process_vor
    """
    quote = _d(ausschussquote_pct)
    if quote < 0 or quote >= 100:
        raise ValueError("ausschussquote_pct muss >= 0 und < 100 sein")
    rate = quote / Decimal("100")
    if rate == 0:
        output = _money(upstream_cost + process_cost_before_scrap)
        return output, _money(Decimal("0")), Decimal("1")
    yield_factor = Decimal("1") / (Decimal("1") - rate)
    output = _money((upstream_cost + process_cost_before_scrap) * yield_factor)
    surcharge = _money(output - upstream_cost - process_cost_before_scrap)
    return output, surcharge, yield_factor

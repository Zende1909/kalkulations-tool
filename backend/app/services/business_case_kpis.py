"""Business-Case-KPIs: Umsatz, operative Kosten, EBIT und ROI.

CAPEX (Werks-/Anlageninvestitionen) ist kapitalbindend, aber nicht EBIT-wirksam.
EBIT basiert auf operativen Kosten (Teile + Nicht-CAPEX-Investitionen).
ROI inkl. CAPEX = EBIT / gebundenes Projektkapital (operative Kosten + CAPEX).
"""

from __future__ import annotations

from typing import Any

# CAPEX wird bewusst nicht in die EBIT-Kostenbasis einbezogen, da Werksinvestitionen
# über die allgemeine Kostenstruktur/Overheads wieder erwirtschaftet werden und
# nicht als laufende Projektkosten behandelt werden.


def _sum_optional(*values: float | None) -> float | None:
    present = [float(v) for v in values if v is not None]
    if not present:
        return None
    return sum(present)


def _sum_positions(positions: list[dict[str, Any]], key: str) -> float | None:
    values = [row.get(key) for row in positions if row.get(key) is not None]
    if not values:
        return None
    return sum(float(v) for v in values)


def _optional_float(value: float | None) -> float | None:
    if value is None:
        return None
    val = float(value)
    return val if val != 0 else None


def _ebit(revenue: float | None, cost: float | None) -> float | None:
    if revenue is None or cost is None:
        return None
    return revenue - cost


def _ratio_pct(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator * 100


def _combine_operating_cost(parts_cost: float | None, operative_inv_cost: float) -> float | None:
    if parts_cost is None and operative_inv_cost == 0:
        return None
    return (parts_cost or 0.0) + operative_inv_cost


def _segment_metrics(
    *,
    cost: float | None,
    bottom_revenue: float | None,
    actual_revenue: float | None,
) -> dict[str, float | None]:
    ebit_bottom = _ebit(bottom_revenue, cost)
    ebit_actual = _ebit(actual_revenue, cost)
    return {
        "cost_total": cost,
        "bottom_price_revenue_total": bottom_revenue,
        "actual_revenue_total": actual_revenue,
        "ebit_bottom": ebit_bottom,
        "ebit_bottom_pct": _ratio_pct(ebit_bottom, bottom_revenue),
        "ebit_actual": ebit_actual,
        "ebit_actual_pct": _ratio_pct(ebit_actual, actual_revenue),
        "roi_bottom_pct": _ratio_pct(ebit_bottom, cost),
        "roi_actual_pct": _ratio_pct(ebit_actual, cost),
    }


def build_business_case_kpis(
    *,
    sales_totals: dict[str, Any],
    investment_financial_summary: dict[str, Any],
    parts: list[dict[str, Any]],
    assemblies: list[dict[str, Any]],
) -> dict[str, Any]:
    """Berechnet Teile-, Investitions- und Gesamt-KPIs inkl. EBIT/ROI."""
    parts_cost = sales_totals.get("cost_total")
    parts_bottom = sales_totals.get("bottom_price_revenue_total")
    parts_actual = sales_totals.get("actual_revenue_total")

    fin = investment_financial_summary
    inv_totals = fin.get("totals") or {}
    inv_capex = fin.get("capex") or {}
    inv_entwicklung = fin.get("entwicklung") or {}
    inv_legacy = fin.get("legacy") or {}

    capex_cost = float(inv_capex.get("cost_amount_total") or 0)
    operative_inv_cost = float(inv_entwicklung.get("cost_amount_total") or 0) + float(
        inv_legacy.get("cost_amount_total") or 0
    )
    total_inv_cost = float(inv_totals.get("cost_amount_total") or 0)

    inv_bottom = _optional_float(inv_totals.get("bottom_price_total"))
    inv_actual = _optional_float(inv_totals.get("revenue_amount_total"))

    parts_cost_f = float(parts_cost) if parts_cost is not None else None
    operative_cost = _combine_operating_cost(parts_cost_f, operative_inv_cost)
    bound_capital = (
        (operative_cost or 0.0) + capex_cost if operative_cost is not None or capex_cost else None
    )

    total_bottom = _sum_optional(
        float(parts_bottom) if parts_bottom is not None else None,
        inv_bottom,
    )
    total_actual = _sum_optional(
        float(parts_actual) if parts_actual is not None else None,
        inv_actual,
    )

    ebit_bottom = _ebit(total_bottom, operative_cost)
    ebit_actual = _ebit(total_actual, operative_cost)

    operating = {
        "cost_total": operative_cost,
        "bottom_price_revenue_total": total_bottom,
        "actual_revenue_total": total_actual,
        "ebit_bottom": ebit_bottom,
        "ebit_bottom_pct": _ratio_pct(ebit_bottom, total_bottom),
        "ebit_actual": ebit_actual,
        "ebit_actual_pct": _ratio_pct(ebit_actual, total_actual),
        "roi_operating_bottom_pct": _ratio_pct(ebit_bottom, operative_cost),
        "roi_operating_actual_pct": _ratio_pct(ebit_actual, operative_cost),
    }

    capital = {
        "capex_total": capex_cost,
        "operative_investment_cost_total": operative_inv_cost,
        "non_capex_investment_cost_total": operative_inv_cost,
        "total_investment_cost_total": total_inv_cost,
        "bound_capital_total": bound_capital,
        "capex_share_of_bound_capital_pct": _ratio_pct(capex_cost, bound_capital),
        "roi_incl_capex_bottom_pct": _ratio_pct(ebit_bottom, bound_capital),
        "roi_incl_capex_actual_pct": _ratio_pct(ebit_actual, bound_capital),
    }

    parts_segment = _segment_metrics(
        cost=parts_cost_f,
        bottom_revenue=float(parts_bottom) if parts_bottom is not None else None,
        actual_revenue=float(parts_actual) if parts_actual is not None else None,
    )
    investments_operating_segment = _segment_metrics(
        cost=operative_inv_cost if operative_inv_cost else None,
        bottom_revenue=inv_bottom,
        actual_revenue=inv_actual,
    )

    total_segment = {
        **operating,
        "roi_bottom_pct": capital["roi_incl_capex_bottom_pct"],
        "roi_actual_pct": capital["roi_incl_capex_actual_pct"],
    }

    return {
        "parts": parts_segment,
        "investments": investments_operating_segment,
        "investments_operating": investments_operating_segment,
        "capex": {
            "cost_total": capex_cost if capex_cost else None,
            "bottom_price_revenue_total": None,
            "actual_revenue_total": None,
            "ebit_bottom": None,
            "ebit_bottom_pct": None,
            "ebit_actual": None,
            "ebit_actual_pct": None,
            "bound_capital_share_pct": capital["capex_share_of_bound_capital_pct"],
            "note": "nicht EBIT-wirksam, kapitalbindend",
        },
        "operating": operating,
        "capital": capital,
        "total": total_segment,
        "revenue_breakdown": {
            "parts_bottom_price_revenue": parts_bottom,
            "parts_actual_revenue": parts_actual,
            "investments_bottom_price_revenue": inv_bottom,
            "investments_actual_revenue": inv_actual,
            "total_bottom_price_revenue": total_bottom,
            "total_actual_revenue": total_actual,
        },
        "cost_breakdown": {
            "parts_standalone": _sum_positions(parts, "cost_total"),
            "assemblies": _sum_positions(assemblies, "cost_total"),
            "parts_total": parts_cost_f,
            "capex": capex_cost,
            "entwicklung": float(inv_entwicklung.get("cost_amount_total") or 0),
            "legacy": float(inv_legacy.get("cost_amount_total") or 0),
            "operative_investments": operative_inv_cost,
            "investments_total": total_inv_cost,
            "operative_total": operative_cost,
            "bound_capital": bound_capital,
            "total": bound_capital,
        },
        "ebit_note": "EBIT basiert auf operativen Kosten ohne CAPEX.",
        "roi_note": (
            "ROI inkl. CAPEX = EBIT / gebundenes Projektkapital (operative Kosten + CAPEX). "
            "Operativer ROI ohne CAPEX = EBIT / operative Kosten."
        ),
    }

"""Business-Case-KPIs: Umsatz, Kosten, EBIT und ROI über Teile und Investitionen."""

from __future__ import annotations

from typing import Any


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


def _roi(revenue: float | None, cost: float | None) -> float | None:
    profit = _ebit(revenue, cost)
    if profit is None or cost is None or cost == 0:
        return None
    return profit / cost * 100


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
        "roi_bottom_pct": _roi(bottom_revenue, cost),
        "roi_actual_pct": _roi(actual_revenue, cost),
    }


def _combine_cost(parts_cost: float | None, inv_cost: float) -> float | None:
    if parts_cost is None and inv_cost == 0:
        return None
    return (parts_cost or 0.0) + inv_cost


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

    inv_cost = float(inv_totals.get("cost_amount_total") or 0)
    inv_bottom = _optional_float(inv_totals.get("bottom_price_total"))
    inv_actual = _optional_float(inv_totals.get("revenue_amount_total"))

    total_cost = _combine_cost(
        float(parts_cost) if parts_cost is not None else None,
        inv_cost,
    )
    total_bottom = _sum_optional(
        float(parts_bottom) if parts_bottom is not None else None,
        inv_bottom,
    )
    total_actual = _sum_optional(
        float(parts_actual) if parts_actual is not None else None,
        inv_actual,
    )

    parts_segment = _segment_metrics(
        cost=float(parts_cost) if parts_cost is not None else None,
        bottom_revenue=float(parts_bottom) if parts_bottom is not None else None,
        actual_revenue=float(parts_actual) if parts_actual is not None else None,
    )
    investments_segment = _segment_metrics(
        cost=inv_cost if inv_cost else None,
        bottom_revenue=inv_bottom,
        actual_revenue=inv_actual,
    )
    total_segment = _segment_metrics(
        cost=total_cost,
        bottom_revenue=total_bottom,
        actual_revenue=total_actual,
    )

    return {
        "parts": parts_segment,
        "investments": investments_segment,
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
            "capex": float(inv_capex.get("cost_amount_total") or 0),
            "entwicklung": float(inv_entwicklung.get("cost_amount_total") or 0),
            "legacy": float(inv_legacy.get("cost_amount_total") or 0),
            "investments_total": inv_cost,
            "total": total_cost,
        },
        "roi_note": (
            "Projektlaufzeit-ROI auf Basis einmaliger Investitionswerte und "
            "stückbezogener Teilekosten über die Projektstückzahl."
        ),
    }

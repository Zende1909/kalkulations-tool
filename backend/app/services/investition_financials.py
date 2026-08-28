"""Einmalige Investitionsbeträge: Kosten, Bottom Price, Erlös und Margen."""

from __future__ import annotations

from typing import Any

from app.services.investition_assignment_service import infer_assignment_type
from app.services.investition_service import is_capex, is_entwicklung, is_legacy_payment


def effective_cost_amount(
    *,
    cost_amount: float | None,
    amount: float | None = None,
) -> float:
    """Kosten – Legacy-Spalte `amount` als Fallback wenn cost_amount leer/0."""
    if cost_amount is not None and cost_amount != 0:
        return float(cost_amount)
    if amount is not None:
        return float(amount)
    if cost_amount is not None:
        return float(cost_amount)
    return 0.0


def _optional_value(value: float | None) -> float | None:
    if value is None:
        return None
    return float(value)


def compute_margin(revenue: float | None, base: float | None) -> float | None:
    if revenue is None or base is None:
        return None
    return revenue - base


def build_amount_warnings(
    *,
    cost_amount: float,
    bottom_price: float | None,
    revenue_amount: float | None,
) -> list[str]:
    warnings: list[str] = []
    bottom = _optional_value(bottom_price)
    revenue = _optional_value(revenue_amount)
    if bottom is not None and bottom < cost_amount:
        warnings.append("Bottom Price liegt unter den Investitionskosten.")
    if revenue is not None and revenue < cost_amount:
        warnings.append("Erlös liegt unter den Investitionskosten.")
    if revenue is not None and bottom is not None and revenue < bottom:
        warnings.append("Erlös liegt unter dem Bottom Price.")
    return warnings


def build_investment_financial_view(
    *,
    cost_amount: float,
    bottom_price: float | None,
    revenue_amount: float | None,
    legacy_amount: float | None = None,
    payment_type: str | None = None,
) -> dict[str, Any]:
    cost = effective_cost_amount(cost_amount=cost_amount, amount=legacy_amount)
    if payment_type is not None and is_capex(payment_type):
        bottom = None
        revenue = None
    else:
        bottom = _optional_value(bottom_price)
        revenue = _optional_value(revenue_amount)
    margin_revenue_cost = compute_margin(revenue, cost)
    margin_revenue_bottom = compute_margin(revenue, bottom)
    margin_bottom_cost = compute_margin(bottom, cost)
    return {
        "cost_amount": cost,
        "bottom_price": bottom,
        "revenue_amount": revenue,
        "margin_revenue_minus_cost": margin_revenue_cost,
        "margin_revenue_minus_bottom_price": margin_revenue_bottom,
        "margin_bottom_price_minus_cost": margin_bottom_cost,
        "warnings": build_amount_warnings(
            cost_amount=cost,
            bottom_price=bottom,
            revenue_amount=revenue,
        ),
    }


def _is_material_assignment(assignment_type: str | None) -> bool:
    return assignment_type in ("einzelteil", "kaufteil", "baugruppe")


def _capex_block(rows_subset: list[dict]) -> dict[str, Any]:
    return {
        "count": len(rows_subset),
        "cost_amount_total": sum(float(r.get("cost_amount") or 0) for r in rows_subset),
        "bottom_price_total": 0.0,
        "revenue_amount_total": 0.0,
        "margin_revenue_minus_cost_total": None,
        "margin_revenue_minus_bottom_price_total": None,
        "margin_bottom_price_minus_cost_total": None,
        "margin_revenue_minus_cost_pct": None,
        "margin_revenue_minus_bottom_price_pct": None,
    }


def _financial_block(rows_subset: list[dict]) -> dict[str, Any]:
    cost_total = sum(float(r.get("cost_amount") or 0) for r in rows_subset)
    revenue_values = [r.get("revenue_amount") for r in rows_subset if r.get("revenue_amount") is not None]
    revenue_total = sum(float(v) for v in revenue_values) if revenue_values else 0.0
    margin_rev_cost = _sum_margins(rows_subset, "margin_revenue_minus_cost")
    margin_rev_bottom = _sum_margins(rows_subset, "margin_revenue_minus_bottom_price")
    return {
        "count": len(rows_subset),
        "cost_amount_total": cost_total,
        "bottom_price_total": _sum(rows_subset, "bottom_price"),
        "revenue_amount_total": revenue_total if revenue_values else 0.0,
        "margin_revenue_minus_cost_total": margin_rev_cost,
        "margin_revenue_minus_bottom_price_total": margin_rev_bottom,
        "margin_bottom_price_minus_cost_total": _sum_margins(
            rows_subset, "margin_bottom_price_minus_cost"
        ),
        "margin_revenue_minus_cost_pct": (
            margin_rev_cost / revenue_total * 100
            if margin_rev_cost is not None and revenue_total
            else None
        ),
        "margin_revenue_minus_bottom_price_pct": (
            margin_rev_bottom / revenue_total * 100
            if margin_rev_bottom is not None and revenue_total
            else None
        ),
    }


def _sum(rows_subset: list[dict], key: str) -> float:
    total = 0.0
    for r in rows_subset:
        val = r.get(key)
        if val is not None:
            total += float(val)
    return total


def _sum_margins(rows_subset: list[dict], key: str) -> float | None:
    values = [r.get(key) for r in rows_subset if r.get(key) is not None]
    if not values:
        return None
    return sum(float(v) for v in values)


def aggregate_investment_financials(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Summiert Beträge und Margen; trennt CAPEX, Entwicklung, Legacy und Zuordnung."""
    capex_rows = [r for r in rows if is_capex(r.get("payment_type") or "")]
    entwicklung_rows = [r for r in rows if is_entwicklung(r.get("payment_type") or "")]
    legacy_rows = [r for r in rows if is_legacy_payment(r.get("payment_type") or "")]
    margin_capable_rows = entwicklung_rows + legacy_rows

    material: list[dict[str, Any]] = []
    project: list[dict[str, Any]] = []
    for row in margin_capable_rows:
        atype = row.get("assignment_type")
        if atype is None:
            atype = infer_assignment_type(
                assignment_type=None,
                calculation_id=row.get("calculation_id"),
                baugruppe_id=row.get("baugruppe_id"),
                kaufteil_id=row.get("kaufteil_id"),
            )
        if _is_material_assignment(atype):
            material.append(row)
        else:
            project.append(row)

    all_cost_total = sum(float(r.get("cost_amount") or 0) for r in rows)
    margin_totals = _financial_block(margin_capable_rows)
    totals = {
        "count": len(rows),
        "cost_amount_total": all_cost_total,
        "bottom_price_total": margin_totals["bottom_price_total"],
        "revenue_amount_total": margin_totals["revenue_amount_total"],
        "margin_revenue_minus_cost_total": margin_totals["margin_revenue_minus_cost_total"],
        "margin_revenue_minus_bottom_price_total": margin_totals[
            "margin_revenue_minus_bottom_price_total"
        ],
        "margin_bottom_price_minus_cost_total": margin_totals[
            "margin_bottom_price_minus_cost_total"
        ],
        "margin_revenue_minus_cost_pct": margin_totals["margin_revenue_minus_cost_pct"],
        "margin_revenue_minus_bottom_price_pct": margin_totals[
            "margin_revenue_minus_bottom_price_pct"
        ],
    }

    return {
        "capex": _capex_block(capex_rows),
        "entwicklung": _financial_block(entwicklung_rows),
        "legacy": _financial_block(legacy_rows),
        "material_assignments": _financial_block(material),
        "project_assignments": _financial_block(project),
        "totals": totals,
    }


def financial_fields_for_export(
    *,
    cost_amount: float | None,
    bottom_price: float | None,
    revenue_amount: float | None,
    legacy_amount: float | None = None,
    payment_type: str | None = None,
) -> dict[str, float | None]:
    """Ungerundete Finanzwerte für Exporte (Excel/PDF/API-Parität)."""
    view = build_investment_financial_view(
        cost_amount=cost_amount or 0.0,
        bottom_price=bottom_price,
        revenue_amount=revenue_amount,
        legacy_amount=legacy_amount,
        payment_type=payment_type,
    )
    return {
        "cost_amount": view["cost_amount"],
        "bottom_price": view["bottom_price"],
        "revenue_amount": view["revenue_amount"],
        "margin_revenue_minus_cost": view["margin_revenue_minus_cost"],
        "margin_revenue_minus_bottom_price": view["margin_revenue_minus_bottom_price"],
        "margin_bottom_price_minus_cost": view["margin_bottom_price_minus_cost"],
    }

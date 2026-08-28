"""Business-Case: Kosten, Richtpreis, manuelle Stückpreise und Margen."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business_case_manual_price import BusinessCaseManualPrice
from app.services.spritzguss_cost_snapshot import selbstkosten_aus_ergebnis

GUIDE_PROFIT_FACTOR = 1.15


def kosten_aus_spritzguss(ergebnis: dict | None) -> float | None:
    return selbstkosten_aus_ergebnis(ergebnis)


def kosten_aus_baugruppe(ergebnis: dict | None) -> float | None:
    if not isinstance(ergebnis, dict):
        return None
    for key in ("herstellkosten", "selbstkosten", "gesamte_herstellkosten"):
        value = ergebnis.get(key)
        if value is not None:
            return float(value)
    return None


def kalkulatorischer_richtpreis(cost_per_piece: float | None) -> float | None:
    if cost_per_piece is None:
        return None
    return cost_per_piece * GUIDE_PROFIT_FACTOR


def _margin_per_piece(price: float | None, cost: float | None) -> float | None:
    if price is None or cost is None:
        return None
    return price - cost


def _price_warnings(
    *,
    cost_per_piece: float | None,
    bottom_price_per_piece: float | None,
    actual_price_per_piece: float | None,
) -> list[str]:
    warnings: list[str] = []
    if bottom_price_per_piece is not None and cost_per_piece is not None:
        if bottom_price_per_piece < cost_per_piece:
            warnings.append("Bottom Price liegt unter den Kosten pro Stück.")
    if actual_price_per_piece is not None and cost_per_piece is not None:
        if actual_price_per_piece < cost_per_piece:
            warnings.append("Tatsächlicher Preis liegt unter den Kosten pro Stück.")
    return warnings


def build_position_pricing(
    *,
    cost_per_piece: float | None,
    bottom_price_per_piece: float | None,
    actual_price_per_piece: float | None,
    project_volume: float,
) -> dict[str, Any]:
    guide = kalkulatorischer_richtpreis(cost_per_piece)
    bottom_revenue = (
        bottom_price_per_piece * project_volume if bottom_price_per_piece is not None else None
    )
    actual_revenue = (
        actual_price_per_piece * project_volume if actual_price_per_piece is not None else None
    )
    cost_total = cost_per_piece * project_volume if cost_per_piece is not None else None
    margin_bottom_piece = _margin_per_piece(bottom_price_per_piece, cost_per_piece)
    margin_actual_piece = _margin_per_piece(actual_price_per_piece, cost_per_piece)
    margin_bottom_total = (
        bottom_revenue - cost_total
        if bottom_revenue is not None and cost_total is not None
        else None
    )
    margin_actual_total = (
        actual_revenue - cost_total
        if actual_revenue is not None and cost_total is not None
        else None
    )
    return {
        "cost_per_piece": cost_per_piece,
        "bottom_price_per_piece": bottom_price_per_piece,
        "actual_price_per_piece": actual_price_per_piece,
        "guide_price_per_piece": guide,
        "project_volume": project_volume,
        "bottom_price_revenue": bottom_revenue,
        "actual_revenue": actual_revenue,
        "cost_total": cost_total,
        "margin_bottom_price_per_piece": margin_bottom_piece,
        "margin_actual_price_per_piece": margin_actual_piece,
        "margin_bottom_price_total": margin_bottom_total,
        "margin_actual_total": margin_actual_total,
        "price_warnings": _price_warnings(
            cost_per_piece=cost_per_piece,
            bottom_price_per_piece=bottom_price_per_piece,
            actual_price_per_piece=actual_price_per_piece,
        ),
        "has_manual_bottom_price": bottom_price_per_piece is not None,
        "has_manual_actual_price": actual_price_per_piece is not None,
    }


def load_manual_prices_map(
    db: Session,
    *,
    customer_id: int,
    program_id: int,
    linked_project_id: int,
) -> dict[tuple[str, int], BusinessCaseManualPrice]:
    rows = db.scalars(
        select(BusinessCaseManualPrice).where(
            BusinessCaseManualPrice.customer_id == customer_id,
            BusinessCaseManualPrice.program_id == program_id,
            BusinessCaseManualPrice.linked_project_id == linked_project_id,
        )
    ).all()
    return {(row.assignment_type, row.object_id): row for row in rows}


def aggregate_sales_totals(positions: list[dict[str, Any]]) -> dict[str, Any]:
    def _sum(key: str) -> float:
        total = 0.0
        for row in positions:
            val = row.get(key)
            if val is not None:
                total += float(val)
        return total

    def _sum_optional(key: str) -> float | None:
        values = [row.get(key) for row in positions if row.get(key) is not None]
        if not values:
            return None
        return sum(float(v) for v in values)

    project_volume = sum(float(row.get("project_volume") or 0) for row in positions)
    return {
        "cost_total": _sum("cost_total"),
        "bottom_price_revenue_total": _sum_optional("bottom_price_revenue"),
        "actual_revenue_total": _sum_optional("actual_revenue"),
        "margin_bottom_price_total": _sum_optional("margin_bottom_price_total"),
        "margin_actual_total": _sum_optional("margin_actual_total"),
        "project_volume_total": project_volume,
        "position_count": len(positions),
    }

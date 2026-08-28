"""Business-Case: Kosten, Richtpreis, manuelle Stückpreise, Margen und Prozentwerte."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.business_case_manual_price import BusinessCaseManualPrice
from app.services.spritzguss_cost_snapshot import (
    herstellkosten_aus_baugruppe,
    selbstkosten_aus_ergebnis,
)

GUIDE_PROFIT_FACTOR = 1.15


def kosten_aus_spritzguss(
    ergebnis: dict | None,
    *,
    bloecke: dict | None = None,
) -> float | None:
    return selbstkosten_aus_ergebnis(ergebnis, bloecke=bloecke)


def kosten_aus_baugruppe(
    ergebnis: dict | None,
    *,
    bloecke: dict | None = None,
) -> float | None:
    return herstellkosten_aus_baugruppe(ergebnis, bloecke=bloecke)


def kalkulatorischer_richtpreis(cost_per_piece: float | None) -> float | None:
    if cost_per_piece is None:
        return None
    return cost_per_piece * GUIDE_PROFIT_FACTOR


def _margin_per_piece(price: float | None, cost: float | None) -> float | None:
    if price is None or cost is None:
        return None
    return price - cost


def margin_percent_on_price(price: float | None, cost: float | None) -> float | None:
    """Marge % = (Preis − Kosten) / Preis × 100."""
    if price is None or cost is None or price == 0:
        return None
    return (price - cost) / price * 100


def revenue_margin_percent(revenue: float | None, base: float | None) -> float | None:
    """Investitionsmarge % = (Erlös − Basis) / Erlös × 100."""
    if revenue is None or base is None or revenue == 0:
        return None
    return (revenue - base) / revenue * 100


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
    margin_bottom_pct = margin_percent_on_price(bottom_price_per_piece, cost_per_piece)
    margin_actual_pct = margin_percent_on_price(actual_price_per_piece, cost_per_piece)
    margin_bottom_total_pct = margin_percent_on_price(bottom_revenue, cost_total) if bottom_revenue else None
    margin_actual_total_pct = margin_percent_on_price(actual_revenue, cost_total) if actual_revenue else None

    return {
        "cost_per_piece": cost_per_piece,
        "has_cost_per_piece": cost_per_piece is not None,
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
        "margin_bottom_price_pct": margin_bottom_pct,
        "margin_actual_price_pct": margin_actual_pct,
        "margin_bottom_price_total_pct": margin_bottom_total_pct,
        "margin_actual_total_pct": margin_actual_total_pct,
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
    def _sum_optional(key: str) -> float | None:
        values = [row.get(key) for row in positions if row.get(key) is not None]
        if not values:
            return None
        return sum(float(v) for v in values)

    def _weighted_margin_pct(
        margin_key: str,
        revenue_key: str,
    ) -> float | None:
        total_revenue = _sum_optional(revenue_key)
        total_margin = _sum_optional(margin_key)
        if total_revenue is None or total_margin is None or total_revenue == 0:
            return None
        return total_margin / total_revenue * 100

    project_volume = sum(float(row.get("project_volume") or 0) for row in positions)
    return {
        "cost_total": _sum_optional("cost_total"),
        "bottom_price_revenue_total": _sum_optional("bottom_price_revenue"),
        "actual_revenue_total": _sum_optional("actual_revenue"),
        "margin_bottom_price_total": _sum_optional("margin_bottom_price_total"),
        "margin_actual_total": _sum_optional("margin_actual_total"),
        "margin_bottom_price_total_pct": _weighted_margin_pct(
            "margin_bottom_price_total", "bottom_price_revenue"
        ),
        "margin_actual_total_pct": _weighted_margin_pct(
            "margin_actual_total", "actual_revenue"
        ),
        "project_volume_total": project_volume,
        "position_count": len(positions),
    }

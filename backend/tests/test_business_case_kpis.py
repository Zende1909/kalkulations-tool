"""Business-Case-KPIs: Umsatz, EBIT und ROI inkl. Investitionserlöse."""

from __future__ import annotations

import pytest

from app.services.business_case_kpis import build_business_case_kpis


def test_investment_revenue_included_in_total_revenue():
    summary = build_business_case_kpis(
        sales_totals={
            "cost_total": 100_000.0,
            "bottom_price_revenue_total": 120_000.0,
            "actual_revenue_total": 130_000.0,
        },
        investment_financial_summary={
            "totals": {
                "cost_amount_total": 50_000.0,
                "bottom_price_total": 60_000.0,
                "revenue_amount_total": 70_000.0,
            },
            "capex": {"cost_amount_total": 20_000.0},
            "entwicklung": {"cost_amount_total": 10_000.0},
            "legacy": {"cost_amount_total": 20_000.0},
        },
        parts=[{"cost_total": 60_000.0}],
        assemblies=[{"cost_total": 40_000.0}],
    )
    assert summary["revenue_breakdown"]["total_bottom_price_revenue"] == 180_000.0
    assert summary["revenue_breakdown"]["total_actual_revenue"] == 200_000.0
    assert summary["total"]["cost_total"] == 150_000.0
    assert summary["total"]["ebit_bottom"] == 30_000.0
    assert summary["total"]["ebit_actual"] == 50_000.0


def test_capex_increases_cost_not_revenue():
    summary = build_business_case_kpis(
        sales_totals={"cost_total": 80_000.0, "bottom_price_revenue_total": 100_000.0},
        investment_financial_summary={
            "totals": {"cost_amount_total": 200_000.0, "bottom_price_total": 0.0, "revenue_amount_total": 0.0},
            "capex": {"cost_amount_total": 200_000.0},
            "entwicklung": {"cost_amount_total": 0.0},
            "legacy": {"cost_amount_total": 0.0},
        },
        parts=[],
        assemblies=[{"cost_total": 80_000.0}],
    )
    assert summary["revenue_breakdown"]["total_bottom_price_revenue"] == 100_000.0
    assert summary["revenue_breakdown"]["investments_bottom_price_revenue"] is None
    assert summary["total"]["cost_total"] == 280_000.0
    assert summary["total"]["ebit_bottom"] == pytest.approx(-180_000.0)


def test_ebit_and_roi_percent():
    summary = build_business_case_kpis(
        sales_totals={"cost_total": 50_000.0, "actual_revenue_total": 100_000.0},
        investment_financial_summary={
            "totals": {"cost_amount_total": 0.0, "bottom_price_total": 0.0, "revenue_amount_total": 0.0},
            "capex": {"cost_amount_total": 0.0},
            "entwicklung": {"cost_amount_total": 0.0},
            "legacy": {"cost_amount_total": 0.0},
        },
        parts=[{"cost_total": 50_000.0}],
        assemblies=[],
    )
    assert summary["parts"]["ebit_actual"] == 50_000.0
    assert summary["parts"]["ebit_actual_pct"] == pytest.approx(50.0)
    assert summary["parts"]["roi_actual_pct"] == pytest.approx(100.0)


def test_roi_division_by_zero():
    summary = build_business_case_kpis(
        sales_totals={},
        investment_financial_summary={
            "totals": {"cost_amount_total": 0.0, "bottom_price_total": 0.0, "revenue_amount_total": 0.0},
            "capex": {"cost_amount_total": 0.0},
            "entwicklung": {"cost_amount_total": 0.0},
            "legacy": {"cost_amount_total": 0.0},
        },
        parts=[],
        assemblies=[],
    )
    assert summary["total"]["roi_bottom_pct"] is None
    assert summary["total"]["roi_actual_pct"] is None


def test_negative_ebit():
    summary = build_business_case_kpis(
        sales_totals={"cost_total": 100_000.0, "bottom_price_revenue_total": 80_000.0},
        investment_financial_summary={
            "totals": {"cost_amount_total": 0.0, "bottom_price_total": 0.0, "revenue_amount_total": 0.0},
            "capex": {"cost_amount_total": 0.0},
            "entwicklung": {"cost_amount_total": 0.0},
            "legacy": {"cost_amount_total": 0.0},
        },
        parts=[],
        assemblies=[],
    )
    assert summary["total"]["ebit_bottom"] == -20_000.0
    assert summary["total"]["ebit_bottom_pct"] == pytest.approx(-25.0)


def test_entwicklung_optional_revenue():
    summary = build_business_case_kpis(
        sales_totals={},
        investment_financial_summary={
            "totals": {
                "cost_amount_total": 40_000.0,
                "bottom_price_total": 45_000.0,
                "revenue_amount_total": 50_000.0,
            },
            "capex": {"cost_amount_total": 0.0},
            "entwicklung": {"cost_amount_total": 40_000.0},
            "legacy": {"cost_amount_total": 0.0},
        },
        parts=[],
        assemblies=[],
    )
    assert summary["investments"]["bottom_price_revenue_total"] == 45_000.0
    assert summary["investments"]["actual_revenue_total"] == 50_000.0
    assert summary["investments"]["ebit_actual"] == 10_000.0

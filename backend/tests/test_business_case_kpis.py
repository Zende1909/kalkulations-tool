"""Business-Case-KPIs: CAPEX-Trennung, EBIT und ROI."""

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
    assert summary["operating"]["cost_total"] == 130_000.0
    assert summary["operating"]["ebit_bottom"] == 50_000.0
    assert summary["capital"]["bound_capital_total"] == 150_000.0


def test_capex_does_not_reduce_ebit():
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
    assert summary["operating"]["cost_total"] == 80_000.0
    assert summary["operating"]["ebit_bottom"] == 20_000.0
    assert summary["capital"]["capex_total"] == 200_000.0
    assert summary["capital"]["bound_capital_total"] == 280_000.0
    assert summary["capital"]["roi_incl_capex_bottom_pct"] == pytest.approx(20_000 / 280_000 * 100)
    assert summary["operating"]["roi_operating_bottom_pct"] == pytest.approx(25.0)


def test_capex_no_revenue():
    summary = build_business_case_kpis(
        sales_totals={},
        investment_financial_summary={
            "totals": {"cost_amount_total": 150_000.0, "bottom_price_total": 0.0, "revenue_amount_total": 0.0},
            "capex": {"cost_amount_total": 150_000.0},
            "entwicklung": {"cost_amount_total": 0.0},
            "legacy": {"cost_amount_total": 0.0},
        },
        parts=[],
        assemblies=[],
    )
    assert summary["revenue_breakdown"]["total_bottom_price_revenue"] is None
    assert summary["capex"]["cost_total"] == 150_000.0
    assert summary["capex"]["note"] == "nicht EBIT-wirksam, kapitalbindend"


def test_entwicklung_reduces_ebit():
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
    assert summary["operating"]["cost_total"] == 40_000.0
    assert summary["operating"]["ebit_actual"] == 10_000.0


def test_legacy_reduces_ebit():
    summary = build_business_case_kpis(
        sales_totals={"cost_total": 30_000.0, "actual_revenue_total": 50_000.0},
        investment_financial_summary={
            "totals": {"cost_amount_total": 20_000.0, "bottom_price_total": 0.0, "revenue_amount_total": 25_000.0},
            "capex": {"cost_amount_total": 0.0},
            "entwicklung": {"cost_amount_total": 0.0},
            "legacy": {"cost_amount_total": 20_000.0},
        },
        parts=[{"cost_total": 30_000.0}],
        assemblies=[],
    )
    assert summary["operating"]["cost_total"] == 50_000.0
    assert summary["operating"]["ebit_actual"] == 25_000.0


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
    assert summary["capital"]["roi_incl_capex_bottom_pct"] is None
    assert summary["operating"]["roi_operating_bottom_pct"] is None


def test_negative_ebit_and_roi():
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
    assert summary["operating"]["ebit_bottom"] == -20_000.0
    assert summary["operating"]["ebit_bottom_pct"] == pytest.approx(-25.0)
    assert summary["operating"]["roi_operating_bottom_pct"] == pytest.approx(-20.0)

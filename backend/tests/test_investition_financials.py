"""Investitionen: Kosten, Bottom Price, Erlös, Margen und Rückwärtskompatibilität."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.business_case import InvestitionSnapshot, build_business_case
from app.services.investition_financials import (
    aggregate_investment_financials,
    build_amount_warnings,
    build_investment_financial_view,
    effective_cost_amount,
    financial_fields_for_export,
)
from app.services.investition_service import validate_investition_input

client = TestClient(app)


def test_effective_cost_amount_prefers_cost_over_legacy():
    assert effective_cost_amount(cost_amount=80_000.0, amount=50_000.0) == 80_000.0


def test_effective_cost_amount_legacy_fallback():
    assert effective_cost_amount(cost_amount=None, amount=42_000.0) == 42_000.0


def test_effective_cost_amount_zero_cost_uses_legacy_amount():
    assert effective_cost_amount(cost_amount=0.0, amount=42_000.0) == 42_000.0


def test_build_financial_view_without_optional_amounts():
    view = build_investment_financial_view(cost_amount=80_000, bottom_price=None, revenue_amount=None)
    assert view["cost_amount"] == 80_000.0
    assert view["bottom_price"] is None
    assert view["revenue_amount"] is None
    assert view["margin_revenue_minus_cost"] is None
    assert view["warnings"] == []


def test_build_financial_view_margins_and_warnings():
    view = build_investment_financial_view(
        cost_amount=80_000,
        bottom_price=90_000,
        revenue_amount=100_000,
    )
    assert view["margin_revenue_minus_cost"] == 20_000.0
    assert view["margin_revenue_minus_bottom_price"] == 10_000.0
    assert view["margin_bottom_price_minus_cost"] == 10_000.0
    assert view["warnings"] == []


def test_negative_margins_produce_warnings():
    warnings = build_amount_warnings(cost_amount=80_000, bottom_price=70_000, revenue_amount=65_000)
    assert "Bottom Price liegt unter den Investitionskosten." in warnings
    assert "Erlös liegt unter den Investitionskosten." in warnings
    assert "Erlös liegt unter dem Bottom Price." in warnings


def test_aggregate_splits_material_and_project():
    rows = [
        {
            "cost_amount": 80_000,
            "bottom_price": 90_000,
            "revenue_amount": 100_000,
            "margin_revenue_minus_cost": 20_000,
            "margin_revenue_minus_bottom_price": 10_000,
            "margin_bottom_price_minus_cost": 10_000,
            "assignment_type": "einzelteil",
        },
        {
            "cost_amount": 50_000,
            "bottom_price": None,
            "revenue_amount": None,
            "margin_revenue_minus_cost": None,
            "margin_revenue_minus_bottom_price": None,
            "margin_bottom_price_minus_cost": None,
            "assignment_type": "gesamtprojekt",
        },
    ]
    summary = aggregate_investment_financials(rows)
    assert summary["material_assignments"]["count"] == 1
    assert summary["material_assignments"]["cost_amount_total"] == 80_000.0
    assert summary["project_assignments"]["count"] == 1
    assert summary["project_assignments"]["cost_amount_total"] == 50_000.0
    assert summary["totals"]["cost_amount_total"] == 130_000.0


def test_business_case_financial_totals():
    rows = [
        InvestitionSnapshot(
            id=1,
            name="Werkzeug",
            investment_type="Werkzeug",
            payment_type="Einmalzahlung",
            amount=80_000,
            amortization_volume=None,
            cost_per_piece=None,
            project_id="P1",
            customer="K1",
            calculation_id=5,
            baugruppe_id=None,
            included_in_unit_price=False,
            archived=False,
            cost_amount=80_000,
            bottom_price=90_000,
            revenue_amount=100_000,
            assignment_type="einzelteil",
        ),
        InvestitionSnapshot(
            id=2,
            name="Projektposten",
            investment_type="Sonstige",
            payment_type="Einmalzahlung",
            amount=20_000,
            amortization_volume=None,
            cost_per_piece=None,
            project_id="P1",
            customer="K1",
            calculation_id=None,
            baugruppe_id=None,
            included_in_unit_price=False,
            archived=False,
            cost_amount=20_000,
            assignment_type="gesamtprojekt",
        ),
    ]
    result = build_business_case(rows, project="P1")
    assert result["investition_cost_total"] == 100_000.0
    assert result["investition_bottom_price_total"] == 90_000.0
    assert result["investition_revenue_total"] == 100_000.0
    assert result["margin_revenue_minus_cost_total"] == 20_000.0
    material = result["investition_financial_summary"]["material_assignments"]
    project = result["investition_financial_summary"]["project_assignments"]
    assert material["cost_amount_total"] == 80_000.0
    assert project["cost_amount_total"] == 20_000.0


def test_validate_investition_input_three_amounts():
    result = validate_investition_input(
        name="Werkzeug",
        investment_type="Werkzeug",
        payment_type="Einmalzahlung",
        cost_amount=80_000,
        bottom_price=90_000,
        revenue_amount=100_000,
        amortization_volume=None,
        project="Projekt Alpha",
    )
    assert result["cost_amount"] == 80_000.0
    assert result["amount"] == 80_000.0
    assert result["bottom_price"] == 90_000.0
    assert result["revenue_amount"] == 100_000.0


def test_financial_fields_for_export_parity():
    fields = financial_fields_for_export(
        cost_amount=80_000,
        bottom_price=90_000,
        revenue_amount=100_000,
    )
    view = build_investment_financial_view(
        cost_amount=80_000,
        bottom_price=90_000,
        revenue_amount=100_000,
    )
    assert fields["cost_amount"] == view["cost_amount"]
    assert fields["margin_revenue_minus_cost"] == view["margin_revenue_minus_cost"]
"""Zahlungsarten CAPEX und Entwicklung: Validierung, Business Case und Export."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


from app.api.router import api_router
from app.core.security import UserRole
from app.database import Base, get_db
from app.dependencies import get_current_user
from app.models import (  # noqa: F401
    Baugruppe,
    Customer,
    Investition,
    Program,
    Project,
    SpritzgussKalkulation,
)
from app.services.business_case_export import build_business_case_export
from app.services.business_case_overview import build_project_business_case
from app.services.investition_financials import aggregate_investment_financials, build_investment_financial_view
from app.services.investition_service import validate_investition_input


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def seeded(db_session: Session):
    customer = Customer(id=1, customer_number="C1", name="OEM A", active=True)
    program = Program(id=10, customer_id=1, program_number="P1", name="Program Alpha", active=True)
    project = Project(
        id=100,
        program_id=10,
        project_number="PR1",
        name="Projekt Alpha",
        component_area="Interior",
        active=True,
    )
    sg = SpritzgussKalkulation(
        id=1,
        teilebezeichnung="Standalone",
        teilenummer="ST-001",
        project_id=100,
        customer_id=1,
        program_id=10,
        jahresstueckzahl=10000,
        teilegewicht_netto_g=100,
        ausschussquote_pct=2,
        materialpreis_pro_kg=2,
        zykluszeit_s=30,
        kavitaeten=1,
        maschinenstundensatz=50,
        lohnstundensatz=25,
        werkzeugkosten_eur=0,
        aktiv=True,
        ergebnis={"selbstkosten": 10.0},
    )
    db_session.add_all([customer, program, project, sg])
    db_session.commit()
    return db_session


@pytest.fixture()
def api_client(seeded: Session):
    app = FastAPI()
    app.include_router(api_router)

    def override_db():
        yield seeded

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id=1,
        role=UserRole.KALKULATOR.value,
        email="test@example.com",
        is_active=True,
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def _base_payload(**overrides):
    payload = {
        "name": "Test",
        "investment_type": "Werkzeug",
        "payment_type": "CAPEX",
        "cost_amount": 120000,
        "customer_id": 1,
        "program_id": 10,
        "linked_project_id": 100,
        "assignment_type": "gesamtprojekt",
        "description": "",
    }
    payload.update(overrides)
    return payload


def test_capex_selectable_and_persisted(api_client: TestClient):
    resp = api_client.post("/api/v1/investitionen", json=_base_payload(name="Anlage CAPEX"))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["payment_type"] == "CAPEX"
    assert body["cost_amount"] == 120000.0
    assert body["bottom_price"] is None
    assert body["revenue_amount"] is None
    assert body["payment_hint"] == "Werksinvestition ohne Bottom Price und Erlös"

    reloaded = api_client.get(f"/api/v1/investitionen/{body['id']}")
    assert reloaded.json()["payment_type"] == "CAPEX"


def test_entwicklung_selectable_and_persisted(api_client: TestClient):
    payload = _base_payload(
        name="Entwicklung komplett",
        payment_type="Entwicklung",
        cost_amount=80000,
        bottom_price=90000,
        revenue_amount=100000,
    )
    resp = api_client.post("/api/v1/investitionen", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["payment_type"] == "Entwicklung"
    assert body["bottom_price"] == 90000.0
    assert body["revenue_amount"] == 100000.0
    assert body["margin_revenue_minus_cost"] == 20000.0


def test_capex_rejects_bottom_price_and_revenue(api_client: TestClient):
    resp = api_client.post(
        "/api/v1/investitionen",
        json=_base_payload(bottom_price=50000, revenue_amount=60000),
    )
    assert resp.status_code == 422
    assert "Bottom Price und Erlös nicht zulässig" in resp.json()["detail"]


def test_capex_requires_positive_cost(api_client: TestClient):
    resp = api_client.post("/api/v1/investitionen", json=_base_payload(cost_amount=0))
    assert resp.status_code == 422


def test_entwicklung_cost_only(api_client: TestClient):
    payload = _base_payload(
        name="Entwicklung minimal",
        payment_type="Entwicklung",
        cost_amount=45000,
    )
    resp = api_client.post("/api/v1/investitionen", json=payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["bottom_price"] is None
    assert body["revenue_amount"] is None


def test_switch_to_capex_clears_optional_amounts(api_client: TestClient, seeded: Session):
    inv = Investition(
        name="Alt",
        investment_type="Werkzeug",
        payment_type="Entwicklung",
        amount=50000,
        cost_amount=50000,
        bottom_price=55000,
        revenue_amount=60000,
        customer_id=1,
        program_id=10,
        linked_project_id=100,
        assignment_type="gesamtprojekt",
        project_id="Projekt Alpha",
        customer="OEM A",
        status="",
    )
    seeded.add(inv)
    seeded.commit()

    resp = api_client.put(
        f"/api/v1/investitionen/{inv.id}",
        json={"payment_type": "CAPEX", "cost_amount": 50000},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["payment_type"] == "CAPEX"
    assert body["bottom_price"] is None
    assert body["revenue_amount"] is None


def test_business_case_separate_sums(seeded: Session):
    seeded.add_all(
        [
            Investition(
                name="CAPEX Anlage",
                investment_type="Maschine",
                payment_type="CAPEX",
                amount=200000,
                cost_amount=200000,
                customer_id=1,
                program_id=10,
                linked_project_id=100,
                assignment_type="gesamtprojekt",
                project_id="Projekt Alpha",
                customer="OEM A",
            ),
            Investition(
                name="Entwicklung",
                investment_type="Sonstige",
                payment_type="Entwicklung",
                amount=80000,
                cost_amount=80000,
                bottom_price=90000,
                revenue_amount=100000,
                customer_id=1,
                program_id=10,
                linked_project_id=100,
                assignment_type="gesamtprojekt",
                project_id="Projekt Alpha",
                customer="OEM A",
            ),
            Investition(
                name="Einmal",
                investment_type="Werkzeug",
                payment_type="Einmalzahlung",
                amount=50000,
                cost_amount=50000,
                bottom_price=55000,
                revenue_amount=60000,
                customer_id=1,
                program_id=10,
                linked_project_id=100,
                assignment_type="einzelteil",
                calculation_id=1,
                part_number="ST-001",
                project_id="Projekt Alpha",
                customer="OEM A",
            ),
        ]
    )
    seeded.commit()

    result = build_project_business_case(
        seeded, customer_id=1, program_id=10, linked_project_id=100
    )
    fin = result["investment_financial_summary"]
    assert fin["capex"]["cost_amount_total"] == 200000.0
    assert fin["entwicklung"]["cost_amount_total"] == 80000.0
    assert fin["legacy"]["cost_amount_total"] == 50000.0
    assert fin["totals"]["cost_amount_total"] == 330000.0
    assert result["kpis"]["investitionen_gesamt"] == 330000.0
    assert len(result["investments_capex"]) == 1
    assert len(result["investments_entwicklung"]) == 1
    assert len(result["investments_other"]) == 1
    capex_row = result["investments_capex"][0]
    assert capex_row["bottom_price"] is None
    assert capex_row["revenue_amount"] is None
    assert capex_row["margin_revenue_minus_cost_pct"] is None


def test_capex_excluded_from_margin_totals():
    rows = [
        {
            "payment_type": "CAPEX",
            "cost_amount": 100000,
            "bottom_price": None,
            "revenue_amount": None,
            "margin_revenue_minus_cost": None,
            "margin_revenue_minus_bottom_price": None,
            "margin_bottom_price_minus_cost": None,
            "assignment_type": "gesamtprojekt",
        },
        {
            "payment_type": "Entwicklung",
            "cost_amount": 50000,
            "bottom_price": 60000,
            "revenue_amount": 80000,
            "margin_revenue_minus_cost": 30000,
            "margin_revenue_minus_bottom_price": 20000,
            "margin_bottom_price_minus_cost": 10000,
            "assignment_type": "gesamtprojekt",
        },
    ]
    summary = aggregate_investment_financials(rows)
    assert summary["totals"]["cost_amount_total"] == 150000.0
    assert summary["totals"]["revenue_amount_total"] == 80000.0
    assert summary["totals"]["margin_revenue_minus_cost_total"] == 30000.0
    assert summary["capex"]["margin_revenue_minus_cost_total"] is None


def test_build_financial_view_capex_strips_optional():
    view = build_investment_financial_view(
        cost_amount=90000,
        bottom_price=95000,
        revenue_amount=100000,
        payment_type="CAPEX",
    )
    assert view["bottom_price"] is None
    assert view["revenue_amount"] is None
    assert view["margin_revenue_minus_cost"] is None


def test_margin_percent_two_decimals():
    view = build_investment_financial_view(
        cost_amount=80_000,
        bottom_price=90_000,
        revenue_amount=100_000,
        payment_type="Entwicklung",
    )
    margin = view["margin_revenue_minus_cost"]
    pct = margin / 100_000 * 100
    assert pct == pytest.approx(20.0)


def test_validate_investition_input_legacy_unchanged():
    result = validate_investition_input(
        name="Alt",
        investment_type="Werkzeug",
        payment_type="Amortisation",
        cost_amount=100000,
        amortization_volume=5000,
        project="Projekt Alpha",
    )
    assert result["cost_per_piece"] == pytest.approx(20.0)
    assert result["amortization_volume"] == 5000


def test_excel_export_includes_payment_type(seeded: Session):
    seeded.add(
        Investition(
            name="CAPEX",
            investment_type="Maschine",
            payment_type="CAPEX",
            amount=75000,
            cost_amount=75000,
            customer_id=1,
            program_id=10,
            linked_project_id=100,
            assignment_type="gesamtprojekt",
            project_id="Projekt Alpha",
            customer="OEM A",
        )
    )
    seeded.commit()
    export = build_business_case_export(
        seeded, customer_id=1, program_id=10, linked_project_id=100
    )
    assert export.investment_headers[0] == "Zahlungsart"
    assert export.investment_rows[0][0] == "CAPEX"

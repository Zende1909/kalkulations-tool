"""Business Case: Hierarchie-Filter, Deduplizierung, Preise und Export."""

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
    BaugruppeSpritzgussZuordnung,
    BusinessCaseManualPrice,
    Customer,
    Investition,
    Program,
    ProgramVolume,
    Project,
    SpritzgussKalkulation,
)
from app.services.business_case_overview import build_project_business_case
from app.services.business_case_pricing import (
    build_position_pricing,
    kalkulatorischer_richtpreis,
)


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
    c1 = Customer(id=1, customer_number="C1", name="OEM A", active=True)
    p1 = Program(id=10, customer_id=1, program_number="P1", name="Program Alpha", active=True)
    pr1 = Project(
        id=100,
        program_id=10,
        project_number="PR1",
        name="Projekt Alpha",
        component_area="Interior",
        quantity_per_vehicle=2,
        active=True,
    )
    db_session.add_all([c1, p1, pr1])
    db_session.add(
        ProgramVolume(id=1, program_id=10, calendar_year=2026, vehicle_volume=1000)
    )
    sg_standalone = SpritzgussKalkulation(
        id=1,
        teilebezeichnung="Standalone",
        teilenummer="ST-001",
        project_id=100,
        customer_id=1,
        program_id=10,
        jahresstueckzahl=5000,
        teilegewicht_netto_g=100,
        ausschussquote_pct=2,
        materialpreis_pro_kg=2,
        zykluszeit_s=30,
        kavitaeten=1,
        maschinenstundensatz=50,
        lohnstundensatz=25,
        werkzeugkosten_eur=0,
        aktiv=True,
        ergebnis={"selbstkosten": 10.0, "endpreis_je_stueck": 12.0},
    )
    sg_in_bg = SpritzgussKalkulation(
        id=2,
        teilebezeichnung="In Baugruppe",
        teilenummer="BG-P-001",
        project_id=100,
        customer_id=1,
        program_id=10,
        jahresstueckzahl=8000,
        teilegewicht_netto_g=100,
        ausschussquote_pct=2,
        materialpreis_pro_kg=2,
        zykluszeit_s=30,
        kavitaeten=1,
        maschinenstundensatz=50,
        lohnstundensatz=25,
        werkzeugkosten_eur=0,
        aktiv=True,
        ergebnis={"selbstkosten": 8.0, "endpreis_je_stueck": 9.5},
    )
    bg = Baugruppe(
        id=3,
        name="Frontmodul",
        teilenummer="BG-001",
        linked_project_id=100,
        project_id=100,
        jahresstueckzahl=4000,
        aktiv=True,
        ergebnis={"herstellkosten": 20.0, "baugruppenpreis_je_stueck": 28.0},
    )
    db_session.add_all([sg_standalone, sg_in_bg, bg])
    db_session.flush()
    db_session.add(
        BaugruppeSpritzgussZuordnung(
            baugruppe_id=3,
            spritzguss_kalkulation_id=2,
            menge=1,
            reihenfolge=1,
            snapshot_preis=8.0,
        )
    )
    db_session.add(
        Investition(
            name="Werkzeug",
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
        )
    )
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


def test_einzelteil_in_baugruppe_excluded(seeded: Session):
    result = build_project_business_case(
        seeded, customer_id=1, program_id=10, linked_project_id=100
    )
    part_ids = [p["id"] for p in result["parts"]]
    assert 1 in part_ids
    assert 2 not in part_ids
    assert result["kpis"]["anzahl_einzelteile_in_baugruppen_ausgeschlossen"] == 1


def test_baugruppe_shown_separately(seeded: Session):
    result = build_project_business_case(
        seeded, customer_id=1, program_id=10, linked_project_id=100
    )
    assert len(result["assemblies"]) == 1
    assert result["assemblies"][0]["cost_per_piece"] == 20.0


def test_guide_price_separate_from_actual():
    guide = kalkulatorischer_richtpreis(10.0)
    assert guide == pytest.approx(11.5)
    pricing = build_position_pricing(
        cost_per_piece=10.0,
        bottom_price_per_piece=12.0,
        actual_price_per_piece=13.0,
        project_volume=1000,
    )
    assert pricing["guide_price_per_piece"] == pytest.approx(11.5)
    assert pricing["actual_price_per_piece"] == 13.0
    assert pricing["bottom_price_revenue"] == 12000.0
    assert pricing["actual_revenue"] == 13000.0
    assert pricing["margin_actual_total"] == 3000.0


def test_no_invented_revenue_without_manual_prices(seeded: Session):
    result = build_project_business_case(
        seeded, customer_id=1, program_id=10, linked_project_id=100
    )
    part = result["parts"][0]
    assert part["bottom_price_revenue"] is None
    assert part["actual_revenue"] is None


def test_manual_price_save_and_reload(api_client: TestClient, seeded: Session):
    payload = {
        "customer_id": 1,
        "program_id": 10,
        "linked_project_id": 100,
        "assignment_type": "einzelteil",
        "object_id": 1,
        "bottom_price_per_piece": 14.0,
        "actual_price_per_piece": 15.5,
    }
    resp = api_client.put("/api/v1/business-cases/manual-prices", json=payload)
    assert resp.status_code == 200, resp.text
    bc = api_client.get(
        "/api/v1/business-cases",
        params={"customer_id": 1, "program_id": 10, "linked_project_id": 100},
    )
    assert bc.status_code == 200
    part = bc.json()["parts"][0]
    assert part["bottom_price_per_piece"] == 14.0
    assert part["actual_price_per_piece"] == 15.5
    assert part["bottom_price_revenue"] == pytest.approx(28000.0)
    assert part["has_manual_bottom_price"] is True


def test_negative_margin_warning(seeded: Session):
    seeded.add(
        BusinessCaseManualPrice(
            customer_id=1,
            program_id=10,
            linked_project_id=100,
            assignment_type="einzelteil",
            object_id=1,
            bottom_price_per_piece=8.0,
            actual_price_per_piece=7.0,
        )
    )
    seeded.commit()
    result = build_project_business_case(
        seeded, customer_id=1, program_id=10, linked_project_id=100
    )
    warnings = result["parts"][0]["price_warnings"]
    assert any("Bottom Price" in w for w in warnings)
    assert any("Tatsächlicher Preis" in w for w in warnings)


def test_investment_hierarchy_fields(seeded: Session):
    result = build_project_business_case(
        seeded, customer_id=1, program_id=10, linked_project_id=100
    )
    inv = result["investments"][0]
    assert inv["cost_amount"] == 50000.0
    assert inv["bottom_price"] == 55000.0
    assert inv["revenue_amount"] == 60000.0
    assert inv["assignment_type"] == "einzelteil"
    assert inv["material_number"] == "ST-001"
    assert inv["customer_name"] == "OEM A"


def test_business_case_api_requires_hierarchy_ids(api_client: TestClient):
    assert api_client.get("/api/v1/business-cases").status_code == 422


def test_business_case_excel_export(api_client: TestClient):
    resp = api_client.get(
        "/api/v1/reports/business-case.xlsx",
        params={"customer_id": 1, "program_id": 10, "linked_project_id": 100},
    )
    assert resp.status_code == 200
    assert "spreadsheetml" in resp.headers["content-type"]


def test_business_case_pdf_export(api_client: TestClient):
    resp = api_client.get(
        "/api/v1/reports/business-case.pdf",
        params={"customer_id": 1, "program_id": 10, "linked_project_id": 100},
    )
    assert resp.status_code == 200
    assert resp.content[:4] == b"%PDF"

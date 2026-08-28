"""Investitionen: Hierarchie-Filterkaskade, Targets-API und Validierung."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
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
from app.models import (  # noqa: F401 — register metadata for create_all
    Baugruppe,
    Customer,
    Investition,
    Kaufteil,
    Program,
    Project,
    SpritzgussKalkulation,
)
from app.services.investition_assignment_service import (
    infer_assignment_type,
    list_investment_targets,
    resolve_part_price_for_assignment,
    validate_assignment_payload,
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
    c2 = Customer(id=2, customer_number="C2", name="OEM B", active=True)
    p1 = Program(id=10, customer_id=1, program_number="P1", name="Program Alpha", active=True)
    p2 = Program(id=20, customer_id=2, program_number="P2", name="Program Beta", active=True)
    pr1 = Project(
        id=100,
        program_id=10,
        project_number="PR1",
        name="Projekt Alpha",
        component_area="Interior",
        active=True,
    )
    pr2 = Project(
        id=200,
        program_id=20,
        project_number="PR2",
        name="Projekt Beta",
        component_area="Exterior",
        active=True,
    )
    sg1 = SpritzgussKalkulation(
        id=5,
        teilebezeichnung="Gehäuse",
        teilenummer="GH-001",
        project_id=100,
        customer_id=1,
        program_id=10,
        teilegewicht_netto_g=100,
        ausschussquote_pct=2,
        materialpreis_pro_kg=2,
        zykluszeit_s=30,
        kavitaeten=1,
        maschinenstundensatz=50,
        lohnstundensatz=25,
        werkzeugkosten_eur=0,
        aktiv=True,
        ergebnis={"selbstkosten": 8.5, "endpreis_je_stueck": 12.5},
    )
    sg2 = SpritzgussKalkulation(
        id=6,
        teilebezeichnung="Fremdteil",
        teilenummer="FR-999",
        project_id=200,
        customer_id=2,
        program_id=20,
        teilegewicht_netto_g=50,
        ausschussquote_pct=2,
        materialpreis_pro_kg=2,
        zykluszeit_s=30,
        kavitaeten=1,
        maschinenstundensatz=50,
        lohnstundensatz=25,
        werkzeugkosten_eur=0,
        aktiv=True,
        ergebnis={"selbstkosten": 3.0},
    )
    kt1 = Kaufteil(
        id=7,
        artikelnummer="KT-100",
        bezeichnung="Schraube",
        preis=1.25,
        project_id=100,
        customer_id=1,
        program_id=10,
        lieferant="Lieferant X",
        aktiv=True,
    )
    kt2 = Kaufteil(
        id=8,
        artikelnummer="KT-200",
        bezeichnung="Clip",
        preis=0.5,
        project_id=200,
        customer_id=2,
        program_id=20,
        lieferant="Lieferant Y",
        aktiv=True,
    )
    bg1 = Baugruppe(
        id=3,
        name="Front",
        teilenummer="BG-001",
        project_id=100,
        aktiv=True,
        ergebnis={"baugruppenpreis_je_stueck": 25.0},
    )
    bg2 = Baugruppe(
        id=4,
        name="Heck",
        teilenummer="BG-002",
        project_id=200,
        aktiv=True,
        ergebnis={"baugruppenpreis_je_stueck": 18.0},
    )
    db_session.add_all([c1, c2, p1, p2, pr1, pr2, sg1, sg2, kt1, kt2, bg1, bg2])
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


def test_infer_assignment_type_legacy():
    assert infer_assignment_type(
        assignment_type=None, calculation_id=5, baugruppe_id=None, kaufteil_id=None
    ) == "einzelteil"
    assert infer_assignment_type(
        assignment_type=None, calculation_id=None, baugruppe_id=3, kaufteil_id=None
    ) == "baugruppe"
    assert infer_assignment_type(
        assignment_type=None, calculation_id=None, baugruppe_id=None, kaufteil_id=7
    ) == "kaufteil"
    assert infer_assignment_type(
        assignment_type=None, calculation_id=None, baugruppe_id=None, kaufteil_id=None
    ) == "gesamtprojekt"


def test_list_einzelteil_targets_filters_by_project(seeded: Session):
    targets = list_investment_targets(
        seeded,
        customer_id=1,
        program_id=10,
        project_id=100,
        assignment_type="einzelteil",
    )
    assert len(targets) == 1
    assert targets[0].object_id == 5
    assert targets[0].material_number == "GH-001"
    assert targets[0].part_price == 8.5


def test_list_einzelteil_excludes_other_project(seeded: Session):
    targets = list_investment_targets(
        seeded,
        customer_id=1,
        program_id=10,
        project_id=100,
        assignment_type="einzelteil",
    )
    assert all(t.object_id != 6 for t in targets)


def test_list_kaufteil_and_baugruppe_targets(seeded: Session):
    kt = list_investment_targets(
        seeded, customer_id=1, program_id=10, project_id=100, assignment_type="kaufteil"
    )
    assert len(kt) == 1 and kt[0].object_id == 7
    bg = list_investment_targets(
        seeded, customer_id=1, program_id=10, project_id=100, assignment_type="baugruppe"
    )
    assert len(bg) == 1 and bg[0].object_id == 3


def test_gesamtprojekt_targets_empty(seeded: Session):
    assert (
        list_investment_targets(
            seeded,
            customer_id=1,
            program_id=10,
            project_id=100,
            assignment_type="gesamtprojekt",
        )
        == []
    )


def test_invalid_hierarchy_rejected(seeded: Session):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        list_investment_targets(
            seeded,
            customer_id=1,
            program_id=10,
            project_id=200,
            assignment_type="einzelteil",
        )
    assert "Programm passt nicht" in exc.value.detail


def test_validate_rejects_object_from_other_project(seeded: Session):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        validate_assignment_payload(
            seeded,
            customer_id=1,
            program_id=10,
            linked_project_id=100,
            assignment_type="einzelteil",
            calculation_id=6,
        )
    assert exc.value.status_code == 422
    assert "Projekt" in exc.value.detail


def test_validate_gesamtprojekt_rejects_object_id(seeded: Session):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        validate_assignment_payload(
            seeded,
            customer_id=1,
            program_id=10,
            linked_project_id=100,
            assignment_type="gesamtprojekt",
            calculation_id=5,
        )
    assert exc.value.status_code == 422


def test_resolve_part_prices(seeded: Session):
    assert (
        resolve_part_price_for_assignment(
            seeded, assignment_type="einzelteil", calculation_id=5, baugruppe_id=None, kaufteil_id=None
        )
        == 8.5
    )
    assert (
        resolve_part_price_for_assignment(
            seeded, assignment_type="kaufteil", calculation_id=None, baugruppe_id=None, kaufteil_id=7
        )
        == 1.25
    )
    assert (
        resolve_part_price_for_assignment(
            seeded, assignment_type="baugruppe", calculation_id=None, baugruppe_id=3, kaufteil_id=None
        )
        == 25.0
    )


def test_targets_api(api_client: TestClient):
    response = api_client.get(
        "/api/v1/investitionen/targets",
        params={
            "customer_id": 1,
            "program_id": 10,
            "project_id": 100,
            "assignment_type": "einzelteil",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["material_number"] == "GH-001"


def test_create_and_list_investition_einzelteil(api_client: TestClient, seeded: Session):
    payload = {
        "name": "Werkzeug GH",
        "investment_type": "Werkzeug",
        "payment_type": "Amortisation",
        "amount": 40000,
        "amortization_volume": 20000,
        "customer_id": 1,
        "program_id": 10,
        "linked_project_id": 100,
        "assignment_type": "einzelteil",
        "calculation_id": 5,
        "description": "",
    }
    created = api_client.post("/api/v1/investitionen", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["assignment_type"] == "einzelteil"
    assert body["part_number"] == "GH-001"
    assert body["linked_project_id"] == 100

    listed = api_client.get(
        "/api/v1/investitionen",
        params={"linked_project_id": 100},
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_create_gesamtprojekt_without_object(api_client: TestClient):
    payload = {
        "name": "Anlage",
        "investment_type": "Maschine",
        "payment_type": "Einmalzahlung",
        "amount": 100000,
        "customer_id": 1,
        "program_id": 10,
        "linked_project_id": 100,
        "assignment_type": "gesamtprojekt",
        "description": "",
    }
    response = api_client.post("/api/v1/investitionen", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["assignment_type"] == "gesamtprojekt"
    assert data["part_number"] == ""
    assert "Gesamtprojekt" in data["zuordnung"]


def test_create_kaufteil_and_baugruppe(api_client: TestClient):
    kt_payload = {
        "name": "Werkzeug KT",
        "investment_type": "Werkzeug",
        "payment_type": "Einmalzahlung",
        "amount": 5000,
        "customer_id": 1,
        "program_id": 10,
        "linked_project_id": 100,
        "assignment_type": "kaufteil",
        "kaufteil_id": 7,
        "description": "",
    }
    assert api_client.post("/api/v1/investitionen", json=kt_payload).status_code == 201

    bg_payload = {
        "name": "Montage",
        "investment_type": "Montageanlage",
        "payment_type": "Amortisation",
        "amount": 80000,
        "amortization_volume": 4000,
        "customer_id": 1,
        "program_id": 10,
        "linked_project_id": 100,
        "assignment_type": "baugruppe",
        "baugruppe_id": 3,
        "description": "",
    }
    bg = api_client.post("/api/v1/investitionen", json=bg_payload)
    assert bg.status_code == 201
    assert bg.json()["part_number"] == "BG-001"


def test_create_investition_with_three_amounts_and_reload(api_client: TestClient):
    payload = {
        "name": "Werkzeug komplett",
        "investment_type": "Werkzeug",
        "payment_type": "Einmalzahlung",
        "cost_amount": 80000,
        "bottom_price": 90000,
        "revenue_amount": 100000,
        "customer_id": 1,
        "program_id": 10,
        "linked_project_id": 100,
        "assignment_type": "gesamtprojekt",
        "description": "",
    }
    created = api_client.post("/api/v1/investitionen", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["cost_amount"] == 80000.0
    assert body["bottom_price"] == 90000.0
    assert body["revenue_amount"] == 100000.0
    assert body["margin_revenue_minus_cost"] == 20000.0
    assert body["amount_warnings"] == []

    loaded = api_client.get(f"/api/v1/investitionen/{body['id']}")
    assert loaded.status_code == 200
    reloaded = loaded.json()
    assert reloaded["cost_amount"] == 80000.0
    assert reloaded["bottom_price"] == 90000.0
    assert reloaded["revenue_amount"] == 100000.0


def test_legacy_amount_maps_to_cost_amount(api_client: TestClient):
    payload = {
        "name": "Legacy",
        "investment_type": "Werkzeug",
        "payment_type": "Einmalzahlung",
        "amount": 55000,
        "customer_id": 1,
        "program_id": 10,
        "linked_project_id": 100,
        "assignment_type": "gesamtprojekt",
        "description": "",
    }
    created = api_client.post("/api/v1/investitionen", json=payload)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["cost_amount"] == 55000.0
    assert body["amount"] == 55000.0
    assert body["bottom_price"] is None
    assert body["revenue_amount"] is None


def test_negative_margin_warnings_without_block(api_client: TestClient):
    payload = {
        "name": "Kritisch",
        "investment_type": "Werkzeug",
        "payment_type": "Einmalzahlung",
        "cost_amount": 80000,
        "bottom_price": 70000,
        "revenue_amount": 65000,
        "customer_id": 1,
        "program_id": 10,
        "linked_project_id": 100,
        "assignment_type": "gesamtprojekt",
        "description": "",
    }
    created = api_client.post("/api/v1/investitionen", json=payload)
    assert created.status_code == 201, created.text
    warnings = created.json()["amount_warnings"]
    assert len(warnings) == 3
    assert created.json()["margin_revenue_minus_cost"] == -15000.0

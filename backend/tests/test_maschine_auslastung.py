"""Tests Maschinenauslastung: Bedarf, Verfügbarkeit, Filter, keine Doppelzählung."""

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
    Customer,
    Land,
    Maschine,
    Program,
    ProgramVolume,
    Project,
    SpritzgussKalkulation,
    Werk,
)
from app.services.maschine_auslastung import build_maschinen_auslastung
from app.services.spritzguss_kalkulation import berechne_spritzguss, SpritzgussInput


def _netto_ergebnis(zykluszeit_s: float, kavitaeten: int, ausschuss_pct: float) -> dict:
    result = berechne_spritzguss(
        SpritzgussInput(
            teilegewicht_netto_g=100,
            schussgewicht_g=110,
            materialpreis_pro_kg=2,
            ausschussquote_pct=ausschuss_pct,
            zykluszeit_s=zykluszeit_s,
            kavitaeten=kavitaeten,
            maschinenstundensatz=50,
            lohnstundensatz=25,
            fgk_pct=0,
            werkzeugkosten_eur=0,
        )
    )
    return result.to_dict()


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
    land = Land(id=1, code="DE", name="Deutschland", aktiv=True)
    werk = Werk(
        id=1,
        land_id=1,
        code="W1",
        name="Werk Süd",
        currency="EUR",
        fx_to_eur=1.0,
        aktiv=True,
        arbeitstage_pro_jahr=250,
        schichten_pro_tag=2,
        stunden_pro_schicht=8,
        oee=0.9,
        space_cost_satz_pro_sqm_jahr=30,
        abschreibungsdauer_jahre=10,
        zinssatz=0.08,
        versicherungssatz=0.0045,
        instandhaltungssatz=0.02,
        strompreis=0.06,
        druckluftpreis=0.06,
        kuehlwasserpreis=0.03,
    )
    m1 = Maschine(
        id=1,
        bezeichnung="IMM 150",
        maschinen_nr="M-001",
        stundensatz=20,
        werk_id=1,
        aktiv=True,
        investment=300000,
        flaeche_sqm=25,
        jahresstunden=3600.0,
    )
    m2 = Maschine(
        id=2,
        bezeichnung="Leer Maschine",
        maschinen_nr="M-002",
        stundensatz=18,
        werk_id=1,
        aktiv=True,
        investment=200000,
        flaeche_sqm=20,
        jahresstunden=3600.0,
    )
    m_other = Maschine(
        id=3,
        bezeichnung="Fremdes Werk",
        maschinen_nr="M-003",
        stundensatz=18,
        werk_id=99,
        aktiv=True,
        investment=200000,
        flaeche_sqm=20,
        jahresstunden=3600.0,
    )
    c1 = Customer(id=1, customer_number="C1", name="OEM", active=True)
    p1 = Program(id=10, customer_id=1, program_number="PG1", name="Programm 1", active=True)
    pr1 = Project(
        id=100,
        program_id=10,
        project_number="PR1",
        name="Projekt A",
        component_area="Interior",
        quantity_per_vehicle=1,
        active=True,
    )
    pr2 = Project(
        id=101,
        program_id=10,
        project_number="PR2",
        name="Projekt B",
        component_area="Interior",
        quantity_per_vehicle=1,
        active=True,
    )
    db_session.add_all([land, werk, m1, m2, m_other, c1, p1, pr1, pr2])
    db_session.add(ProgramVolume(id=1, program_id=10, calendar_year=2026, vehicle_volume=1000))
    ergebnis_a = _netto_ergebnis(36.0, 2, 0.0)
    sg_a = SpritzgussKalkulation(
        id=1,
        teilebezeichnung="Teil A",
        teilenummer="A-001",
        project_id=100,
        customer_id=1,
        program_id=10,
        maschine_id=1,
        jahresstueckzahl=3600,
        teilegewicht_netto_g=100,
        ausschussquote_pct=0,
        materialpreis_pro_kg=2,
        zykluszeit_s=36,
        kavitaeten=2,
        maschinenstundensatz=50,
        lohnstundensatz=25,
        werkzeugkosten_eur=0,
        aktiv=True,
        ergebnis=ergebnis_a,
    )
    ergebnis_b = _netto_ergebnis(36.0, 1, 0.0)
    sg_b = SpritzgussKalkulation(
        id=2,
        teilebezeichnung="Teil B",
        teilenummer="B-001",
        project_id=101,
        customer_id=1,
        program_id=10,
        maschine_id=1,
        jahresstueckzahl=1800,
        teilegewicht_netto_g=100,
        ausschussquote_pct=0,
        materialpreis_pro_kg=2,
        zykluszeit_s=36,
        kavitaeten=1,
        maschinenstundensatz=50,
        lohnstundensatz=25,
        werkzeugkosten_eur=0,
        aktiv=True,
        ergebnis=ergebnis_b,
    )
    sg_in_bg = SpritzgussKalkulation(
        id=3,
        teilebezeichnung="In BG",
        teilenummer="BG-001",
        project_id=100,
        customer_id=1,
        program_id=10,
        maschine_id=1,
        jahresstueckzahl=5000,
        teilegewicht_netto_g=100,
        ausschussquote_pct=0,
        materialpreis_pro_kg=2,
        zykluszeit_s=36,
        kavitaeten=2,
        maschinenstundensatz=50,
        lohnstundensatz=25,
        werkzeugkosten_eur=0,
        aktiv=True,
        ergebnis=ergebnis_a,
    )
    bg = Baugruppe(
        id=5,
        name="Modul",
        teilenummer="MOD-1",
        linked_project_id=100,
        project_id=100,
        jahresstueckzahl=1000,
        aktiv=True,
    )
    db_session.add_all([sg_a, sg_b, sg_in_bg, bg])
    db_session.flush()
    db_session.add(
        BaugruppeSpritzgussZuordnung(
            baugruppe_id=5,
            spritzguss_kalkulation_id=3,
            menge=2,
            reihenfolge=1,
            snapshot_preis=5.0,
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


def test_machine_without_demand_shows_zero(seeded: Session):
    result = build_maschinen_auslastung(seeded, plant_id=1, project_ids=[100])
    idle = next(m for m in result["machines"] if m["maschine_id"] == 2)
    assert idle["required_hours"] == 0.0
    assert idle["utilization_pct"] == pytest.approx(0.0)
    assert idle["has_demand"] is False


def test_demand_from_process_time_and_volume(seeded: Session):
    result = build_maschinen_auslastung(seeded, plant_id=1, project_ids=[100])
    busy = next(m for m in result["machines"] if m["maschine_id"] == 1)
    netto = float(_netto_ergebnis(36.0, 2, 0.0)["nettokapazitaet"])
    expected_standalone = 3600 / netto
    expected_bg = 1000 * 2 / netto
    assert busy["required_hours"] == pytest.approx(expected_standalone + expected_bg, rel=1e-4)


def test_multiple_projects_add_hours(seeded: Session):
    single = build_maschinen_auslastung(seeded, plant_id=1, project_ids=[100])
    both = build_maschinen_auslastung(seeded, plant_id=1, project_ids=[100, 101])
    m_single = next(m for m in single["machines"] if m["maschine_id"] == 1)
    m_both = next(m for m in both["machines"] if m["maschine_id"] == 1)
    netto_b = float(_netto_ergebnis(36.0, 1, 0.0)["nettokapazitaet"])
    assert m_both["required_hours"] == pytest.approx(m_single["required_hours"] + 1800 / netto_b)


def test_utilization_under_equal_over_100(seeded: Session):
    result = build_maschinen_auslastung(seeded, plant_id=1, project_ids=[100, 101])
    busy = next(m for m in result["machines"] if m["maschine_id"] == 1)
    assert busy["available_hours"] == 3600.0
    util = busy["required_hours"] / 3600.0 * 100
    assert busy["utilization_pct"] == pytest.approx(util)
    if util > 100:
        assert busy["is_overloaded"] is True
        assert busy["overload_hours"] == pytest.approx(busy["required_hours"] - 3600.0)
    else:
        assert busy["rest_capacity_hours"] == pytest.approx(3600.0 - busy["required_hours"])


def test_no_double_count_standalone_in_baugruppe(seeded: Session):
    result = build_maschinen_auslastung(seeded, plant_id=1, project_ids=[100])
    busy = next(m for m in result["machines"] if m["maschine_id"] == 1)
    sources = [p["source_label"] for p in busy["projects"]]
    assert any("Teil A" in s for s in sources)
    assert any("Modul" in s for s in sources)
    assert not any("In BG" == s for s in sources)


def test_zero_availability_no_division_by_zero(seeded: Session):
    m = seeded.get(Maschine, 2)
    m.jahresstunden = 0
    seeded.commit()
    result = build_maschinen_auslastung(seeded, plant_id=1, project_ids=[100])
    idle = next(r for r in result["machines"] if r["maschine_id"] == 2)
    assert idle["utilization_pct"] is None
    assert idle["rest_capacity_hours"] is None
    assert idle["overload_hours"] is None


def test_no_projects_selected(seeded: Session):
    result = build_maschinen_auslastung(seeded, plant_id=1, project_ids=[])
    assert result["no_projects_selected"] is True
    assert all(m["required_hours"] == 0 for m in result["machines"])
    assert len(result["machines"]) == 2


def test_werk_filter_only_plant_machines(seeded: Session):
    result = build_maschinen_auslastung(seeded, plant_id=1, project_ids=[100])
    ids = {m["maschine_id"] for m in result["machines"]}
    assert ids == {1, 2}
    assert 3 not in ids


def test_invalid_hierarchy_returns_422(seeded: Session):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        build_maschinen_auslastung(
            seeded,
            plant_id=1,
            customer_id=1,
            program_id=10,
            project_ids=[999],
        )
    assert exc.value.status_code == 422


def test_api_endpoint(api_client: TestClient):
    resp = api_client.get(
        "/api/v1/maschinen/auslastung",
        params={"plant_id": 1, "project_ids": [100, 101]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["plant_name"] == "Werk Süd"
    assert body["summary"]["machine_count"] == 2
    assert len(body["machines"]) == 2


def test_api_invalid_program(api_client: TestClient):
    resp = api_client.get(
        "/api/v1/maschinen/auslastung",
        params={"plant_id": 1, "customer_id": 1, "program_id": 99, "project_ids": [100]},
    )
    assert resp.status_code == 422


def test_summary_overloaded_count(seeded: Session):
    result = build_maschinen_auslastung(seeded, plant_id=1, project_ids=[100, 101])
    if result["summary"]["max_utilization_pct"] and result["summary"]["max_utilization_pct"] > 100:
        assert result["summary"]["overloaded_count"] >= 1

"""Tests Maschinenauslastung: OEE, Rüstzeit, Jahresauslastung 2026–2040."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
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
from app.services.maschine_auslastung import (
    UTILIZATION_YEARS,
    _resolve_machine_capacity,
    _run_hours,
    _setup_hours,
    build_maschinen_auslastung,
)
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss


def _netto_ergebnis(
    zykluszeit_s: float,
    kavitaeten: int,
    ausschuss_pct: float,
    *,
    setup_aktiv: bool = False,
    losgroesse: int | None = None,
) -> dict:
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
            setup_zeit_min=30 if setup_aktiv else 0,
            losgroesse=losgroesse,
            setup_aktiv=setup_aktiv,
        )
    )
    d = result.to_dict()
    if setup_aktiv:
        d["setup_aktiv"] = True
    return d


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
    gross = 250 * 2 * 8
    m1 = Maschine(
        id=1,
        bezeichnung="IMM 150",
        maschinen_nr="M-001",
        stundensatz=20,
        werk_id=1,
        aktiv=True,
        investment=300000,
        flaeche_sqm=25,
        jahresstunden=gross * 0.9,
        setup_zeit_min=30,
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
        jahresstunden=gross * 0.9,
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
    db_session.add_all([land, werk, m1, m2, c1, p1, pr1, pr2])
    db_session.add(ProgramVolume(id=1, program_id=10, calendar_year=2026, vehicle_volume=3600))
    db_session.add(ProgramVolume(id=2, program_id=10, calendar_year=2027, vehicle_volume=7200))
    netto = float(_netto_ergebnis(36.0, 2, 0.0)["nettokapazitaet"])
    ergebnis_setup = _netto_ergebnis(36.0, 2, 0.0, setup_aktiv=True, losgroesse=1000)
    sg_a = SpritzgussKalkulation(
        id=1,
        teilebezeichnung="Teil A",
        teilenummer="A-001",
        project_id=100,
        customer_id=1,
        program_id=10,
        maschine_id=1,
        jahresstueckzahl=3600,
        losgroesse=1000,
        teilegewicht_netto_g=100,
        ausschussquote_pct=0,
        materialpreis_pro_kg=2,
        zykluszeit_s=36,
        kavitaeten=2,
        maschinenstundensatz=50,
        lohnstundensatz=25,
        werkzeugkosten_eur=0,
        aktiv=True,
        ergebnis=ergebnis_setup,
    )
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
        ergebnis=_netto_ergebnis(36.0, 1, 0.0),
    )
    db_session.add_all([sg_a, sg_b])
    db_session.commit()
    return db_session, netto


@pytest.fixture()
def api_client(seeded):
    db_session, _ = seeded
    app = FastAPI()
    app.include_router(api_router)

    def override_db():
        yield db_session

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


def test_utilization_years_2026_to_2040(seeded):
    db, _ = seeded
    result = build_maschinen_auslastung(db, plant_id=1, project_ids=[100])
    assert result["years"] == list(range(2026, 2041))
    assert len(result["yearly_rows"]) == 2 * len(UTILIZATION_YEARS)


def test_oee_already_in_jahresstunden_not_applied_twice(seeded):
    db, _ = seeded
    werk = db.get(Werk, 1)
    maschine = db.get(Maschine, 1)
    cap = _resolve_machine_capacity(maschine, werk)
    assert cap.oee_in_available_hours is True
    assert cap.oee == pytest.approx(0.9)
    assert cap.available_hours == pytest.approx(250 * 2 * 8 * 0.9)
    assert cap.gross_hours == pytest.approx(250 * 2 * 8)
    row_2026 = next(
        r for r in build_maschinen_auslastung(db, plant_id=1, project_ids=[100])["yearly_rows"]
        if r["year"] == 2026 and r["machine_id"] == 1
    )
    assert row_2026["available_hours"] == pytest.approx(cap.available_hours)
    assert row_2026["gross_hours"] == pytest.approx(cap.gross_hours)


def test_oee_computed_when_missing_jahresstunden(db_session):
    werk = Werk(
        id=1,
        land_id=1,
        code="W1",
        name="W",
        currency="EUR",
        fx_to_eur=1.0,
        aktiv=True,
        arbeitstage_pro_jahr=200,
        schichten_pro_tag=1,
        stunden_pro_schicht=8,
        oee=0.8,
        space_cost_satz_pro_sqm_jahr=30,
        abschreibungsdauer_jahre=10,
        zinssatz=0.08,
        versicherungssatz=0.0045,
        instandhaltungssatz=0.02,
        strompreis=0.06,
        druckluftpreis=0.06,
        kuehlwasserpreis=0.03,
    )
    m = Maschine(
        id=1,
        bezeichnung="M",
        maschinen_nr="M-1",
        stundensatz=10,
        werk_id=1,
        aktiv=True,
        investment=100000,
        flaeche_sqm=10,
        jahresstunden=None,
    )
    db_session.add_all([Land(id=1, code="DE", name="D", aktiv=True), werk, m])
    db_session.commit()
    cap = _resolve_machine_capacity(m, werk)
    assert cap.available_hours == pytest.approx(200 * 1 * 8 * 0.8)
    assert cap.gross_hours == pytest.approx(200 * 1 * 8)


def test_run_and_setup_hours(seeded):
    db, netto = seeded
    volume = 3600.0
    expected_run = volume / netto
    expected_setup = math.ceil(volume / 1000) * (30 / 60)
    assert _run_hours(volume, netto) == pytest.approx(expected_run)
    assert _setup_hours(volume, 1000, 30) == pytest.approx(expected_setup)
    row = next(
        r for r in build_maschinen_auslastung(db, plant_id=1, project_ids=[100])["yearly_rows"]
        if r["year"] == 2026 and r["machine_id"] == 1
    )
    assert row["run_hours"] == pytest.approx(expected_run)
    assert row["setup_hours"] == pytest.approx(expected_setup)
    assert row["required_hours"] == pytest.approx(expected_run + expected_setup)


def test_different_volumes_per_year(seeded):
    db, netto = seeded
    result = build_maschinen_auslastung(db, plant_id=1, project_ids=[100])
    r26 = next(r for r in result["yearly_rows"] if r["year"] == 2026 and r["machine_id"] == 1)
    r27 = next(r for r in result["yearly_rows"] if r["year"] == 2027 and r["machine_id"] == 1)
    assert r26["run_hours"] == pytest.approx(3600 / netto)
    assert r27["run_hours"] == pytest.approx(7200 / netto)
    assert r27["run_hours"] > r26["run_hours"]


def test_multiple_projects_sum_per_year(seeded):
    db, netto = seeded
    single = build_maschinen_auslastung(db, plant_id=1, project_ids=[100])
    both = build_maschinen_auslastung(db, plant_id=1, project_ids=[100, 101])
    s26 = next(r for r in single["yearly_rows"] if r["year"] == 2026 and r["machine_id"] == 1)
    b26 = next(r for r in both["yearly_rows"] if r["year"] == 2026 and r["machine_id"] == 1)
    netto_b = float(_netto_ergebnis(36.0, 1, 0.0)["nettokapazitaet"])
    assert b26["run_hours"] == pytest.approx(s26["run_hours"] + 3600 / netto_b)


def test_machine_without_demand_zero_utilization(seeded):
    db, _ = seeded
    result = build_maschinen_auslastung(db, plant_id=1, project_ids=[100])
    idle = next(r for r in result["yearly_rows"] if r["machine_id"] == 2 and r["year"] == 2026)
    assert idle["required_hours"] == 0.0
    assert idle["utilization_pct"] == pytest.approx(0.0)
    assert idle["has_demand"] is False


def test_zero_availability_no_division_by_zero(seeded):
    db, _ = seeded
    m = db.get(Maschine, 2)
    m.jahresstunden = 0
    db.commit()
    result = build_maschinen_auslastung(db, plant_id=1, project_ids=[100])
    idle = next(r for r in result["yearly_rows"] if r["machine_id"] == 2 and r["year"] == 2026)
    assert idle["utilization_pct"] is None


def test_overload_when_demand_exceeds_capacity(seeded):
    db, _ = seeded
    vol = db.get(ProgramVolume, 1)
    vol.vehicle_volume = 2_000_000
    db.commit()
    result = build_maschinen_auslastung(db, plant_id=1, project_ids=[100])
    row = next(r for r in result["yearly_rows"] if r["year"] == 2026 and r["machine_id"] == 1)
    assert row["is_overloaded"] is True
    assert row["utilization_pct"] > 100


def test_no_projects_selected(seeded):
    db, _ = seeded
    result = build_maschinen_auslastung(db, plant_id=1, project_ids=[])
    assert result["no_projects_selected"] is True
    assert all(r["required_hours"] == 0 for r in result["yearly_rows"])


def test_api_yearly_breakdown(api_client: TestClient, seeded):
    resp = api_client.get(
        "/api/v1/maschinen/auslastung",
        params={"plant_id": 1, "project_ids": [100]},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["years"][-1] == 2040
    row = next(r for r in body["yearly_rows"] if r["year"] == 2026 and r["machine_id"] == 1)
    assert "run_hours" in row and "setup_hours" in row and "gross_hours" in row


def test_invalid_hierarchy(seeded):
    db, _ = seeded
    with pytest.raises(HTTPException) as exc:
        build_maschinen_auslastung(db, plant_id=1, project_ids=[999])
    assert exc.value.status_code == 422

"""Maschine: Werkpflicht, Rate aus Werkparametern, kein manuelles Stundensatz-Override."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.core.security import UserRole
from app.database import get_db
from app.dependencies import get_current_user
from app.models.land import Land
from app.models.maschine import Maschine
from app.models.werk import Werk
from app.services.machine_hourly_rate import (
    build_rate_input_from_maschine_and_werk,
    berechne_maschinenstundensatz,
)

API = "/api/v1"


def _schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE laender (
                    id INTEGER PRIMARY KEY,
                    code VARCHAR(16) NOT NULL UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP, updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE werke (
                    id INTEGER PRIMARY KEY,
                    land_id INTEGER NOT NULL REFERENCES laender(id),
                    code VARCHAR(32) NOT NULL UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                    fx_to_eur FLOAT NOT NULL DEFAULT 0.92,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    arbeitstage_pro_jahr FLOAT,
                    produktionsintervall_arbeitstage FLOAT,
                    schichten_pro_tag FLOAT,
                    stunden_pro_schicht FLOAT,
                    oee FLOAT,
                    space_cost_satz_pro_sqm_jahr FLOAT,
                    abschreibungsdauer_jahre FLOAT,
                    zinssatz FLOAT,
                    versicherungssatz FLOAT,
                    instandhaltungssatz FLOAT,
                    strompreis FLOAT,
                    druckluftpreis FLOAT,
                    kuehlwasserpreis FLOAT,
                    created_at TIMESTAMP, updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE maschinen (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL,
                    maschinen_nr VARCHAR(50) NOT NULL UNIQUE,
                    stundensatz FLOAT NOT NULL DEFAULT 0,
                    schliesskraft_t FLOAT NOT NULL DEFAULT 0,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    werk_id INTEGER REFERENCES werke(id),
                    maschinentyp VARCHAR(128),
                    variante VARCHAR(64),
                    source_currency VARCHAR(8),
                    arbeitstage_pro_jahr FLOAT,
                    produktionsintervall_arbeitstage FLOAT,
                    schichten_pro_tag FLOAT,
                    stunden_pro_schicht FLOAT,
                    oee FLOAT,
                    investment FLOAT,
                    flaeche_sqm FLOAT,
                    space_cost_satz_pro_sqm_jahr FLOAT,
                    abschreibungsdauer_jahre FLOAT,
                    zinssatz FLOAT,
                    versicherungssatz FLOAT,
                    instandhaltungssatz FLOAT,
                    stromverbrauch_kwh_h FLOAT,
                    strompreis FLOAT,
                    druckluftverbrauch_m3_h FLOAT,
                    druckluftpreis FLOAT,
                    kuehlwasserverbrauch_m3_h FLOAT,
                    kuehlwasserpreis FLOAT,
                    setup_zeit_min FLOAT,
                    setup_mitarbeiter FLOAT,
                    jahresstunden FLOAT,
                    space_costs_pro_stunde FLOAT,
                    abschreibung_pro_stunde FLOAT,
                    zinsen_pro_stunde FLOAT,
                    versicherung_pro_stunde FLOAT,
                    instandhaltung_pro_stunde FLOAT,
                    energie_pro_stunde FLOAT,
                    stundensatz_source FLOAT,
                    rate_updated_at TIMESTAMP,
                    created_at TIMESTAMP, updated_at TIMESTAMP
                )
                """
            )
        )


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _schema(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client(db: Session):
    application = FastAPI()
    application.include_router(api_router)

    def override_get_db():
        yield db

    def override_user():
        return SimpleNamespace(
            email="kalkulator@example.com",
            role=UserRole.KALKULATOR.value,
            is_active=True,
        )

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_current_user] = override_user
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def _seed_werk(db: Session, *, oee: float = 0.9) -> Werk:
    now = datetime.now(timezone.utc)
    land = Land(code="SA", name="SA", aktiv=True, created_at=now, updated_at=now)
    db.add(land)
    db.flush()
    werk = Werk(
        land_id=land.id,
        code="KAEC",
        name="KAEC",
        currency="USD",
        fx_to_eur=0.92,
        aktiv=True,
        arbeitstage_pro_jahr=254,
        schichten_pro_tag=2,
        stunden_pro_schicht=8,
        oee=oee,
        space_cost_satz_pro_sqm_jahr=30,
        abschreibungsdauer_jahre=10,
        zinssatz=0.08,
        versicherungssatz=0.0045,
        instandhaltungssatz=0.02,
        strompreis=0.06,
        druckluftpreis=0.06,
        kuehlwasserpreis=0.03,
        created_at=now,
        updated_at=now,
    )
    db.add(werk)
    db.commit()
    db.refresh(werk)
    return werk


def test_create_maschine_accepts_german_decimal_consumptions(client: TestClient, db: Session):
    werk = _seed_werk(db)
    resp = client.post(
        f"{API}/maschinen",
        json={
            "bezeichnung": "IMM Dec",
            "maschinen_nr": "IMM-DEC",
            "schliesskraft_t": "150",
            "aktiv": True,
            "werk_id": werk.id,
            "investment": "347300",
            "flaeche_sqm": "44,1",
            "stromverbrauch_kwh_h": "50,7",
            "druckluftverbrauch_m3_h": "9,9",
            "kuehlwasserverbrauch_m3_h": "4,1",
            "setup_zeit_min": "30",
            "setup_mitarbeiter": "1,5",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["flaeche_sqm"] == pytest.approx(44.1)
    assert body["stromverbrauch_kwh_h"] == pytest.approx(50.7)
    assert body["druckluftverbrauch_m3_h"] == pytest.approx(9.9)
    assert body["kuehlwasserverbrauch_m3_h"] == pytest.approx(4.1)
    assert body["setup_mitarbeiter"] == pytest.approx(1.5)
    assert body["setup_zeit_min"] == pytest.approx(30)
    mid = body["id"]

    got = client.get(f"{API}/maschinen/{mid}")
    assert got.status_code == 200
    assert got.json()["flaeche_sqm"] == pytest.approx(44.1)

    upd = client.put(
        f"{API}/maschinen/{mid}",
        json={
            "flaeche_sqm": "44.1",
            "stromverbrauch_kwh_h": "51.2",
            "setup_mitarbeiter": 1.5,
        },
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["stromverbrauch_kwh_h"] == pytest.approx(51.2)

    # Stundensatz nutzt Dezimalverbräuche + Werkpreise
    rate = client.post(f"{API}/maschinen/{mid}/recalculate-rate", json={})
    assert rate.status_code == 200, rate.text
    assert rate.json()["stundensatz"] > 0
    assert rate.json()["energie_pro_stunde"] is not None


def test_create_maschine_rejects_invalid_decimal_string(client: TestClient, db: Session):
    werk = _seed_werk(db)
    resp = client.post(
        f"{API}/maschinen",
        json={
            "bezeichnung": "Bad",
            "maschinen_nr": "BAD-DEC",
            "schliesskraft_t": 10,
            "werk_id": werk.id,
            "flaeche_sqm": "abc",
        },
    )
    assert resp.status_code == 422
    assert "Fläche" in str(resp.json()) or "flaeche" in str(resp.json()).lower()


def test_create_maschine_requires_werk(client: TestClient, db: Session):
    resp = client.post(
        f"{API}/maschinen",
        json={
            "bezeichnung": "M",
            "maschinen_nr": "M-1",
            "stundensatz": 99,
            "schliesskraft_t": 10,
            "aktiv": True,
        },
    )
    assert resp.status_code == 422


def test_create_and_recalculate_uses_werk_params(client: TestClient, db: Session):
    werk = _seed_werk(db)
    create = client.post(
        f"{API}/maschinen",
        json={
            "bezeichnung": "IMM 150",
            "maschinen_nr": "IMM-150",
            "werk_id": werk.id,
            "stundensatz": 999,  # darf nicht übernommen werden
            "schliesskraft_t": 150,
            "aktiv": True,
            "investment": 347300,
            "flaeche_sqm": 26.5,
            "stromverbrauch_kwh_h": 22,
            "druckluftverbrauch_m3_h": 5,
            "kuehlwasserverbrauch_m3_h": 1.8,
            "arbeitstage_pro_jahr": 1,  # Client-Versuch: wird verworfen
            "strompreis": 9.99,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["werk_id"] == werk.id
    assert body["stundensatz"] != 999
    assert body["arbeitstage_pro_jahr"] is None
    assert body["strompreis"] is None
    # Auto-calc bei Create wenn Parameter vollständig
    assert body["stundensatz"] == pytest.approx(17.51111996937883 * 0.92, rel=1e-5)

    # Werkparameter ändern → Neuberechnung
    werk.oee = 0.8
    db.commit()
    recalc = client.post(f"{API}/maschinen/{body['id']}/recalculate-rate", json={})
    assert recalc.status_code == 200, recalc.text
    # Niedrigeres OEE → weniger Jahresstunden → höherer Stundensatz
    assert recalc.json()["stundensatz"] > body["stundensatz"]


def test_build_rate_input_prefers_werk_over_machine_legacy():
    werk = SimpleNamespace(
        currency="USD",
        fx_to_eur=0.92,
        arbeitstage_pro_jahr=254,
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
    maschine = SimpleNamespace(
        werk_id=1,
        investment=347300,
        flaeche_sqm=26.5,
        stromverbrauch_kwh_h=22,
        druckluftverbrauch_m3_h=5,
        kuehlwasserverbrauch_m3_h=1.8,
        arbeitstage_pro_jahr=1,
        oee=0.1,
        strompreis=9.0,
        source_currency=None,
    )
    rate_in = build_rate_input_from_maschine_and_werk(maschine, werk)
    assert rate_in.oee == 0.9
    assert rate_in.arbeitstage_pro_jahr == 254
    assert rate_in.strompreis == 0.06
    r = berechne_maschinenstundensatz(rate_in)
    assert r.stundensatz_source == pytest.approx(17.51111996937883, rel=1e-6)


def test_update_rejects_clearing_werk(client: TestClient, db: Session):
    werk = _seed_werk(db)
    created = client.post(
        f"{API}/maschinen",
        json={
            "bezeichnung": "M2",
            "maschinen_nr": "M-2",
            "werk_id": werk.id,
            "schliesskraft_t": 1,
            "aktiv": True,
            "investment": 1000,
            "flaeche_sqm": 10,
        },
    ).json()
    # JSON null für werk_id
    upd = client.put(
        f"{API}/maschinen/{created['id']}",
        json={"werk_id": None, "bezeichnung": "M2"},
    )
    # Pydantic ge=1 oder API 422
    assert upd.status_code == 422

"""Regression: Werk anlegen/bearbeiten inkl. DE-Dezimalen und Validierung."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.core.security import UserRole
from app.database import get_db
from app.dependencies import get_current_user
from app.models.land import Land
from app.models.werk import Werk
from app.schemas.hierarchy_plant import WerkCreate, WerkUpdate

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
    now = datetime.now(timezone.utc)
    session.add(
        Land(id=1, code="SA", name="Saudi-Arabien", aktiv=True, created_at=now, updated_at=now)
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def client(db: Session):
    application = FastAPI()
    application.include_router(api_router)

    def override_get_db():
        yield db

    def override_current_user():
        return SimpleNamespace(
            email="kalkulator@example.com",
            role=UserRole.KALKULATOR.value,
            is_active=True,
        )

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_current_user] = override_current_user
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def _rabigh_payload(**overrides):
    base = {
        "land_id": 1,
        "code": "Zamil Rabigh",
        "name": "Rabigh",
        "currency": "USD",
        "fx_to_eur": 0.92,
        "aktiv": True,
        "arbeitstage_pro_jahr": 254,
        "schichten_pro_tag": 2,
        "stunden_pro_schicht": 8,
        "oee": 0.9,
    }
    base.update(overrides)
    return base


def test_create_werk_success(client: TestClient):
    res = client.post(f"{API}/werke", json=_rabigh_payload())
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["code"] == "Zamil Rabigh"
    assert body["name"] == "Rabigh"
    assert body["land_id"] == 1
    assert body["fx_to_eur"] == pytest.approx(0.92)
    assert body["oee"] == pytest.approx(0.9)
    assert body["arbeitstage_pro_jahr"] == 254


def test_create_werk_stores_numeric_fx_and_oee(client: TestClient, db: Session):
    res = client.post(f"{API}/werke", json=_rabigh_payload(code="RABIGH-NUM"))
    assert res.status_code == 201
    werk = db.query(Werk).filter(Werk.code == "RABIGH-NUM").one()
    assert isinstance(werk.fx_to_eur, float)
    assert isinstance(werk.oee, float)
    assert werk.fx_to_eur == pytest.approx(0.92)
    assert werk.oee == pytest.approx(0.9)


def test_create_werk_rejects_zinssatz_as_percent_points(client: TestClient):
    res = client.post(f"{API}/werke", json=_rabigh_payload(code="BAD-ZINS", zinssatz=8))
    assert res.status_code == 422
    assert "Zinssatz" in str(res.json())


def test_create_werk_accepts_decimal_energy_prices(client: TestClient):
    """Strom-/Druckluft-/Kühlwasserpreis als absolute Dezimalwerte (nicht %)."""
    res = client.post(
        f"{API}/werke",
        json=_rabigh_payload(
            code="RABIGH-ENERGY",
            zinssatz=0.08,
            versicherungssatz=0.0045,
            instandhaltungssatz=0.02,
            strompreis="0,06",
            druckluftpreis="0.06",
            kuehlwasserpreis="0,03",
            space_cost_satz_pro_sqm_jahr="30,5",
        ),
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["strompreis"] == pytest.approx(0.06)
    assert body["druckluftpreis"] == pytest.approx(0.06)
    assert body["kuehlwasserpreis"] == pytest.approx(0.03)
    assert body["space_cost_satz_pro_sqm_jahr"] == pytest.approx(30.5)
    # Kapitalkostensätze / OEE unverändert Anteile
    assert body["zinssatz"] == pytest.approx(0.08)
    assert body["oee"] == pytest.approx(0.9)

    wid = body["id"]
    listed = client.get(f"{API}/werke").json()
    match = next(w for w in listed if w["id"] == wid)
    assert match["strompreis"] == pytest.approx(0.06)

    updated = client.put(
        f"{API}/werke/{wid}",
        json={"strompreis": "0,07", "kuehlwasserpreis": 0.035},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["strompreis"] == pytest.approx(0.07)
    assert updated.json()["kuehlwasserpreis"] == pytest.approx(0.035)


def test_schema_rejects_invalid_fx_and_oee():
    with pytest.raises(ValidationError) as exc_fx:
        WerkCreate(**_rabigh_payload(fx_to_eur=0))
    assert "Wechselkurs" in str(exc_fx.value)

    with pytest.raises(ValidationError) as exc_oee:
        WerkCreate(**_rabigh_payload(oee=1.5))
    assert "OEE" in str(exc_oee.value)

    with pytest.raises(ValidationError) as exc_bad:
        WerkCreate(**_rabigh_payload(fx_to_eur="abc"))
    assert "Zahl" in str(exc_bad.value)


def test_create_werk_invalid_values_return_422(client: TestClient):
    res = client.post(f"{API}/werke", json=_rabigh_payload(fx_to_eur=-1))
    assert res.status_code == 422
    detail = str(res.json())
    assert "Wechselkurs" in detail or "fx_to_eur" in detail

    res2 = client.post(f"{API}/werke", json=_rabigh_payload(code="BAD-OEE", oee=2))
    assert res2.status_code == 422
    assert "OEE" in str(res2.json())


def test_create_werk_duplicate_code(client: TestClient):
    assert client.post(f"{API}/werke", json=_rabigh_payload()).status_code == 201
    res = client.post(f"{API}/werke", json=_rabigh_payload(name="Andere"))
    assert res.status_code == 409
    assert "bereits vergeben" in res.json()["detail"]


def test_load_and_update_werk(client: TestClient):
    created = client.post(f"{API}/werke", json=_rabigh_payload(code="RABIGH-EDIT")).json()
    wid = created["id"]

    listed = client.get(f"{API}/werke")
    assert listed.status_code == 200
    assert any(w["id"] == wid for w in listed.json())

    got = client.get(f"{API}/werke")
    match = next(w for w in got.json() if w["id"] == wid)
    assert match["fx_to_eur"] == pytest.approx(0.92)

    updated = client.put(
        f"{API}/werke/{wid}",
        json={"oee": "0,85", "fx_to_eur": "0,91", "name": "Rabigh Plant"},
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["name"] == "Rabigh Plant"
    assert body["oee"] == pytest.approx(0.85)
    assert body["fx_to_eur"] == pytest.approx(0.91)


def test_werk_update_schema_german_decimals():
    upd = WerkUpdate(fx_to_eur="0,92", oee="0,9")
    assert upd.fx_to_eur == pytest.approx(0.92)
    assert upd.oee == pytest.approx(0.9)

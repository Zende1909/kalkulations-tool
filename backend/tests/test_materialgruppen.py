"""CRUD-Tests für Materialgruppen-Stammdaten."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.core.security import UserRole
from app.database import get_db
from app.dependencies import get_current_user
from app.models.material import Material
from app.services.material_thermik import MATERIALGRUPPEN_DEFAULTS
from tests.materialgruppen_test_helpers import create_material_tables, seed_materialgruppen

API = "/api/v1"


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    create_material_tables(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    seed_materialgruppen(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db: Session) -> TestClient:
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


def test_list_materialgruppen_enthaelt_seed(client: TestClient):
    res = client.get(f"{API}/materialgruppen")
    assert res.status_code == 200, res.text
    gruppen = {row["gruppe"]: row for row in res.json()}
    assert len(gruppen) == len(MATERIALGRUPPEN_DEFAULTS)
    assert gruppen["POM"]["schmelzdichte_kg_m3"] == pytest.approx(783.17)


def test_create_materialgruppe(client: TestClient):
    res = client.post(
        f"{API}/materialgruppen",
        json={
            "gruppe": "peek",
            "bezeichnung": "Polyetheretherketon",
            "schmelzdichte_kg_m3": "1300",
            "waermekapazitaet_j_kg_k": "1500",
            "waermeleitfaehigkeit_w_m_k": "0,25",
            "werkzeugtemperatur_c": "160",
            "schmelzetemperatur_c": "380",
            "entformungstemperatur_c": "200",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["gruppe"] == "PEEK"
    assert body["bezeichnung"] == "Polyetheretherketon"


def test_create_duplikat_wird_abgelehnt(client: TestClient):
    res = client.post(
        f"{API}/materialgruppen",
        json={
            "gruppe": "POM",
            "bezeichnung": "Duplikat",
            "schmelzdichte_kg_m3": 800,
            "waermekapazitaet_j_kg_k": 3000,
            "waermeleitfaehigkeit_w_m_k": 0.27,
            "werkzeugtemperatur_c": 40,
            "schmelzetemperatur_c": 220,
            "entformungstemperatur_c": 80,
        },
    )
    assert res.status_code == 409


def test_material_kann_neue_gruppe_waehlen(client: TestClient, db: Session):
    create = client.post(
        f"{API}/materialgruppen",
        json={
            "gruppe": "PEEK",
            "bezeichnung": "Polyetheretherketon",
            "schmelzdichte_kg_m3": 1300,
            "waermekapazitaet_j_kg_k": 1500,
            "waermeleitfaehigkeit_w_m_k": 0.25,
            "werkzeugtemperatur_c": 160,
            "schmelzetemperatur_c": 380,
            "entformungstemperatur_c": 200,
        },
    )
    assert create.status_code == 201

    mat = client.post(
        f"{API}/materialien",
        json={
            "bezeichnung": "PEEK 450G",
            "material_nr": "PEEK-1",
            "preis_pro_kg": "18,00",
            "dichte": "1,31",
            "materialgruppe": "peek",
        },
    )
    assert mat.status_code == 201, mat.text
    assert mat.json()["materialgruppe"] == "PEEK"


def test_loeschen_mit_materialbezug_wird_abgelehnt(client: TestClient, db: Session):
    pom = client.get(f"{API}/materialgruppen?nur_aktiv=false").json()
    pom_id = next(row["id"] for row in pom if row["gruppe"] == "POM")
    db.add(
        Material(
            bezeichnung="Delrin",
            material_nr="POM-DEL",
            preis_pro_kg=2.1,
            dichte=1.41,
            materialgruppe="POM",
        )
    )
    db.commit()

    res = client.delete(f"{API}/materialgruppen/{pom_id}")
    assert res.status_code == 409
    assert "verwendet" in res.text


def test_umbenennung_aktualisiert_materialien(client: TestClient, db: Session):
    create = client.post(
        f"{API}/materialgruppen",
        json={
            "gruppe": "TESTX",
            "bezeichnung": "Testgruppe",
            "schmelzdichte_kg_m3": 900,
            "waermekapazitaet_j_kg_k": 2500,
            "waermeleitfaehigkeit_w_m_k": 0.2,
            "werkzeugtemperatur_c": 50,
            "schmelzetemperatur_c": 230,
            "entformungstemperatur_c": 90,
        },
    )
    gruppe_id = create.json()["id"]
    db.add(
        Material(
            bezeichnung="Testteil",
            material_nr="TX-1",
            preis_pro_kg=2.0,
            dichte=1.2,
            materialgruppe="TESTX",
        )
    )
    db.commit()

    upd = client.put(f"{API}/materialgruppen/{gruppe_id}", json={"gruppe": "TESTY"})
    assert upd.status_code == 200, upd.text
    material = db.scalar(select(Material).where(Material.material_nr == "TX-1"))
    assert material is not None
    assert material.materialgruppe == "TESTY"

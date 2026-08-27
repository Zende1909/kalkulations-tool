"""Material-Stammdaten: DE/EN-Dezimalpreise und Dichte."""

from __future__ import annotations

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
from app.models.material import Material
from app.schemas.material import MaterialCreate, MaterialUpdate

API = "/api/v1"


def _schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE materialien (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL,
                    material_nr VARCHAR(50) NOT NULL UNIQUE,
                    preis_pro_kg FLOAT NOT NULL,
                    dichte FLOAT NOT NULL,
                    waehrung VARCHAR(8) NOT NULL DEFAULT 'EUR',
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
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


def test_schema_accepts_german_and_english_decimals():
    a = MaterialCreate(
        bezeichnung="PA6",
        material_nr="PA6-1",
        preis_pro_kg="2,10",
        dichte="1,04",
    )
    assert a.preis_pro_kg == pytest.approx(2.1)
    assert a.dichte == pytest.approx(1.04)

    b = MaterialCreate(
        bezeichnung="PA6",
        material_nr="PA6-2",
        preis_pro_kg="2.10",
        dichte="1.0400",
    )
    assert b.preis_pro_kg == pytest.approx(2.1)


def test_schema_rejects_invalid_preis():
    with pytest.raises(ValidationError) as exc:
        MaterialCreate(
            bezeichnung="X",
            material_nr="X",
            preis_pro_kg="abc",
            dichte=1,
        )
    assert "Preis pro kg" in str(exc.value)


def test_create_update_reload_material_decimals(client: TestClient, db: Session):
    res = client.post(
        f"{API}/materialien",
        json={
            "bezeichnung": "PA6 GF30",
            "material_nr": "MAT-DEC",
            "preis_pro_kg": "2,10",
            "dichte": "1,04",
            "waehrung": "EUR",
            "aktiv": True,
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["preis_pro_kg"] == pytest.approx(2.1)
    assert body["dichte"] == pytest.approx(1.04)
    mid = body["id"]

    got = client.get(f"{API}/materialien/{mid}")
    assert got.status_code == 200
    assert got.json()["preis_pro_kg"] == pytest.approx(2.1)

    upd = client.put(
        f"{API}/materialien/{mid}",
        json={"preis_pro_kg": "2.1234", "dichte": "0,955"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["preis_pro_kg"] == pytest.approx(2.1234)
    assert upd.json()["dichte"] == pytest.approx(0.955)

    row = db.query(Material).filter(Material.id == mid).one()
    assert row.preis_pro_kg == pytest.approx(2.1234)


def test_material_update_schema_allows_partial_decimals():
    upd = MaterialUpdate(preis_pro_kg="2,50")
    assert upd.preis_pro_kg == pytest.approx(2.5)

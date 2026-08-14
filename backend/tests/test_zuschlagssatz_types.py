"""Tests für Zuschlagssatz-Typen und TOP_LEVEL-Seed."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.core.security import UserRole
from app.database import get_db
from app.dependencies import get_current_user
from app.models.zuschlagssatz import (
    ALLOWED_ZUSCHLAGSSATZ_TYPEN,
    ASSEMBLY_MARKUP_TYPEN,
    STAMMDATEN_ZUSCHLAGSSATZ_TYPEN,
    Zuschlagssatz,
)
from app.schemas.zuschlagssatz import ZuschlagssatzCreate
from app.scripts.seed_top_level_markup_rates import (
    is_local_development_database,
    seed_top_level_markup_rates,
)
from app.services.assembly_recalculation_service import load_global_markup_rates


def _create_zuschlagssatz_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS zuschlagssaetze (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                    satz_prozent FLOAT NOT NULL DEFAULT 0,
                    typ VARCHAR(50) NOT NULL DEFAULT '',
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    _create_zuschlagssatz_schema(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def client(db):
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


@pytest.mark.parametrize("typ", ALLOWED_ZUSCHLAGSSATZ_TYPEN)
def test_zuschlagssatz_create_schema_accepts_allowed_types(typ):
    payload = ZuschlagssatzCreate(bezeichnung=typ, satz_prozent=0, typ=typ, aktiv=True)
    assert payload.typ == typ


def test_zuschlagssatz_create_schema_rejects_unknown_type():
    with pytest.raises(ValidationError):
        ZuschlagssatzCreate(bezeichnung="X", satz_prozent=1, typ="unbekannt", aktiv=True)


@pytest.mark.parametrize("typ", ASSEMBLY_MARKUP_TYPEN)
def test_api_accepts_assembly_markup_types(client, typ):
    response = client.post(
        "/api/v1/zuschlagssaetze",
        json={"bezeichnung": typ, "satz_prozent": 0, "typ": typ, "aktiv": True},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["typ"] == typ
    assert body["aktiv"] is True
    assert body["satz_prozent"] == pytest.approx(0.0)


@pytest.mark.parametrize("typ", STAMMDATEN_ZUSCHLAGSSATZ_TYPEN)
def test_api_still_accepts_stammdaten_types(client, typ):
    response = client.post(
        "/api/v1/zuschlagssaetze",
        json={"bezeichnung": typ, "satz_prozent": 1.5, "typ": typ, "aktiv": True},
    )
    assert response.status_code == 201
    assert response.json()["typ"] == typ


def test_api_rejects_unknown_type(client):
    response = client.post(
        "/api/v1/zuschlagssaetze",
        json={"bezeichnung": "X", "satz_prozent": 1, "typ": "UNGUELTIG", "aktiv": True},
    )
    assert response.status_code == 422


def test_api_update_can_deactivate_assembly_markup(client):
    created = client.post(
        "/api/v1/zuschlagssaetze",
        json={"bezeichnung": "VVGK", "satz_prozent": 10, "typ": "vvgk", "aktiv": True},
    )
    item_id = created.json()["id"]
    response = client.put(
        f"/api/v1/zuschlagssaetze/{item_id}",
        json={"aktiv": False},
    )
    assert response.status_code == 200
    assert response.json()["aktiv"] is False
    assert response.json()["typ"] == "vvgk"


def test_seed_inserts_rates_and_is_idempotent(db):
    db.execute(
        text(
            "INSERT INTO zuschlagssaetze (id, bezeichnung, satz_prozent, typ, aktiv) "
            "VALUES (1, 'MGK', 5, 'GEMEINKOSTEN', 1), (2, 'VVGK', 8, 'GEMEINKOSTEN', 1)"
        )
    )
    db.commit()

    first = seed_top_level_markup_rates(db)
    assert first == ["insert:vvgk", "insert:gewinn", "insert:skonto"]
    second = seed_top_level_markup_rates(db)
    assert second == ["skip:vvgk", "skip:gewinn", "skip:skonto"]

    by_typ = {
        typ: db.execute(
            text("SELECT COUNT(*) FROM zuschlagssaetze WHERE typ = :typ"),
            {"typ": typ},
        ).scalar()
        for (typ,) in db.execute(text("SELECT DISTINCT typ FROM zuschlagssaetze")).all()
    }
    assert by_typ["GEMEINKOSTEN"] == 2
    assert by_typ["vvgk"] == 1
    assert by_typ["gewinn"] == 1
    assert by_typ["skonto"] == 1

    gemeinkosten = db.execute(
        text("SELECT id, bezeichnung, typ, satz_prozent FROM zuschlagssaetze WHERE typ = 'GEMEINKOSTEN' ORDER BY id")
    ).all()
    assert gemeinkosten == [(1, "MGK", "GEMEINKOSTEN", 5.0), (2, "VVGK", "GEMEINKOSTEN", 8.0)]

    skonto = db.execute(
        text("SELECT satz_prozent, aktiv FROM zuschlagssaetze WHERE typ = 'skonto'")
    ).one()
    assert skonto[0] == pytest.approx(0.0)
    assert bool(skonto[1]) is True


def test_uppercase_gewinn_is_not_assembly_markup(db):
    db.add(Zuschlagssatz(bezeichnung="Katalog-Gewinn", satz_prozent=99, typ="GEWINN", aktiv=True))
    db.commit()
    rates = load_global_markup_rates(db)
    assert rates.vvgk_pct is None
    assert rates.gewinn_pct is None
    assert rates.skonto_pct is None


def test_inactive_assembly_markup_is_missing(db):
    db.add(Zuschlagssatz(bezeichnung="VVGK", satz_prozent=10, typ="vvgk", aktiv=False))
    db.add(Zuschlagssatz(bezeichnung="Gewinn", satz_prozent=15, typ="gewinn", aktiv=True))
    db.add(Zuschlagssatz(bezeichnung="Skonto", satz_prozent=0, typ="skonto", aktiv=True))
    db.commit()
    rates = load_global_markup_rates(db)
    assert rates.vvgk_pct is None
    assert rates.gewinn_pct == pytest.approx(15.0)
    assert rates.skonto_pct == pytest.approx(0.0)


def test_frontend_form_options_include_all_types():
    path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "constants"
        / "zuschlagssatzTypen.ts"
    )
    source = path.read_text(encoding="utf-8")
    for typ in ALLOWED_ZUSCHLAGSSATZ_TYPEN:
        assert f'"{typ}"' in source or f"'{typ}'" in source


def test_local_database_guard_allows_localhost():
    assert is_local_development_database("postgresql://postgres:x@localhost:5432/kalkulationstool")
    assert is_local_development_database("postgresql://postgres:x@127.0.0.1:5432/kalkulationstool")
    assert not is_local_development_database("postgresql://postgres:x@prod.example.com:5432/kalkulationstool")

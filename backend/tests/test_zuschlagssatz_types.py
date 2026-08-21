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
    assert_local_development_database,
    is_local_development_database,
    main as seed_markup_main,
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
    assert first == [
        "insert:mgk_kaufteil_selbst",
        "insert:mgk_kaufteil_oem",
        "insert:fgk",
        "insert:vvgk",
        "insert:gewinn",
        "insert:skonto",
    ]
    second = seed_top_level_markup_rates(db)
    assert second == [
        "skip:mgk_kaufteil_selbst",
        "skip:mgk_kaufteil_oem",
        "skip:fgk",
        "skip:vvgk",
        "skip:gewinn",
        "skip:skonto",
    ]

    by_typ = {
        typ: db.execute(
            text("SELECT COUNT(*) FROM zuschlagssaetze WHERE typ = :typ"),
            {"typ": typ},
        ).scalar()
        for (typ,) in db.execute(text("SELECT DISTINCT typ FROM zuschlagssaetze")).all()
    }
    assert by_typ["GEMEINKOSTEN"] == 2
    assert by_typ["vvgk"] == 1
    assert by_typ["fgk"] == 1
    assert by_typ["mgk_kaufteil_selbst"] == 1

    gemeinkosten = db.execute(
        text("SELECT id, bezeichnung, typ, satz_prozent FROM zuschlagssaetze WHERE typ = 'GEMEINKOSTEN' ORDER BY id")
    ).all()
    assert gemeinkosten == [(1, "MGK", "GEMEINKOSTEN", 5.0), (2, "VVGK", "GEMEINKOSTEN", 8.0)]

    skonto = db.execute(
        text("SELECT satz_prozent, aktiv FROM zuschlagssaetze WHERE typ = 'skonto'")
    ).one()
    assert skonto[0] == pytest.approx(0.0)
    assert bool(skonto[1]) is True


def test_seed_leaves_stammdaten_gewinn_and_verschrottung_unchanged(db):
    db.execute(
        text(
            "INSERT INTO zuschlagssaetze (id, bezeichnung, satz_prozent, typ, aktiv) VALUES "
            "(1, 'Katalog-Gewinn', 12.5, 'GEWINN', 1), "
            "(2, 'Ausschuss', 3.0, 'VERSCHROTTUNG', 1), "
            "(3, 'MGK', 5.0, 'GEMEINKOSTEN', 1)"
        )
    )
    db.commit()

    assert seed_top_level_markup_rates(db) == [
        "insert:mgk_kaufteil_selbst",
        "insert:mgk_kaufteil_oem",
        "insert:fgk",
        "insert:vvgk",
        "insert:gewinn",
        "insert:skonto",
    ]

    rows = db.execute(
        text(
            "SELECT id, bezeichnung, typ, satz_prozent, aktiv FROM zuschlagssaetze "
            "WHERE typ IN ('GEWINN', 'VERSCHROTTUNG', 'GEMEINKOSTEN') ORDER BY id"
        )
    ).all()
    assert rows == [
        (1, "Katalog-Gewinn", "GEWINN", 12.5, 1),
        (2, "Ausschuss", "VERSCHROTTUNG", 3.0, 1),
        (3, "MGK", "GEMEINKOSTEN", 5.0, 1),
    ]
    # lowercase gewinn is a separate assembly markup row
    assert (
        db.execute(text("SELECT COUNT(*) FROM zuschlagssaetze WHERE typ = 'gewinn'")).scalar() == 1
    )


def test_uppercase_gewinn_is_not_assembly_markup(db):
    db.add(Zuschlagssatz(bezeichnung="Katalog-Gewinn", satz_prozent=99, typ="GEWINN", aktiv=True))
    db.commit()
    from app.services.assembly_recalculation_service import AssemblyRecalculationError

    with pytest.raises(AssemblyRecalculationError, match="Fehlende aktive Zuschlagssätze"):
        load_global_markup_rates(db)


def test_inactive_assembly_markup_is_missing(db):
    db.add(Zuschlagssatz(bezeichnung="VVGK", satz_prozent=10, typ="vvgk", aktiv=False))
    db.add(Zuschlagssatz(bezeichnung="Gewinn", satz_prozent=15, typ="gewinn", aktiv=True))
    db.add(Zuschlagssatz(bezeichnung="Skonto", satz_prozent=0, typ="skonto", aktiv=True))
    db.add(Zuschlagssatz(bezeichnung="FGK", satz_prozent=22, typ="fgk", aktiv=True))
    db.add(
        Zuschlagssatz(
            bezeichnung="MGK selbst", satz_prozent=3, typ="mgk_kaufteil_selbst", aktiv=True
        )
    )
    db.add(
        Zuschlagssatz(bezeichnung="MGK OEM", satz_prozent=5, typ="mgk_kaufteil_oem", aktiv=True)
    )
    db.commit()
    from app.services.assembly_recalculation_service import AssemblyRecalculationError

    with pytest.raises(AssemblyRecalculationError, match="vvgk"):
        load_global_markup_rates(db)


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


def test_local_database_guard_allows_localhost_and_sqlite():
    assert is_local_development_database("postgresql://postgres:x@localhost:5432/kalkulationstool")
    assert is_local_development_database("postgresql://postgres:x@127.0.0.1:5432/kalkulationstool")
    assert is_local_development_database("sqlite://")
    assert not is_local_development_database("postgresql://postgres:x@prod.example.com:5432/kalkulationstool")
    with pytest.raises(RuntimeError, match="lokale"):
        assert_local_development_database("postgresql://u:p@db.example.com:5432/prod")


def test_startup_does_not_call_markup_seed():
    main_source = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(
        encoding="utf-8"
    )
    assert "seed_top_level_markup_rates" not in main_source
    assert "seed_top_level" not in main_source


def test_cli_rejects_non_local_database(monkeypatch: pytest.MonkeyPatch, capsys):
    from app.config import settings

    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql+psycopg2://u:p@db.example.com:5432/prod",
        raising=False,
    )
    # Fail-fast: no SessionLocal before local check.
    monkeypatch.setattr(
        "app.database.SessionLocal",
        lambda: (_ for _ in ()).throw(AssertionError("SessionLocal must not open")),
    )
    assert seed_markup_main([]) == 1
    err = capsys.readouterr().err.lower()
    assert "abgelehnt" in err
    assert "lokal" in err


def test_cli_seed_success_and_idempotent(monkeypatch: pytest.MonkeyPatch, capsys, db):
    from app.config import settings

    engine = db.get_bind()
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite://", raising=False)
    monkeypatch.setattr("app.database.SessionLocal", Session)

    assert seed_markup_main([]) == 0
    out1 = capsys.readouterr().out
    assert "insert:vvgk" in out1
    assert "insert:fgk" in out1
    assert "insert:mgk_kaufteil_selbst" in out1
    assert "insert:gewinn" in out1
    assert "insert:skonto" in out1

    assert seed_markup_main([]) == 0
    out2 = capsys.readouterr().out
    assert "skip:vvgk" in out2
    assert "skip:fgk" in out2
    assert "skip:gewinn" in out2
    assert "skip:skonto" in out2

    with Session() as check:
        counts = {
            typ: check.execute(
                text("SELECT COUNT(*) FROM zuschlagssaetze WHERE typ = :typ AND aktiv = 1"),
                {"typ": typ},
            ).scalar()
            for typ in (
                "mgk_kaufteil_selbst",
                "mgk_kaufteil_oem",
                "fgk",
                "vvgk",
                "gewinn",
                "skonto",
            )
        }
    assert counts == {
        "mgk_kaufteil_selbst": 1,
        "mgk_kaufteil_oem": 1,
        "fgk": 1,
        "vvgk": 1,
        "gewinn": 1,
        "skonto": 1,
    }


def test_alembic_versions_have_no_markup_seed_dml():
    versions_dir = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    for path in versions_dir.glob("*.py"):
        source = path.read_text(encoding="utf-8").upper()
        assert "INSERT INTO ZUSCHLAGSSAETZE" not in source
        assert "INSERT INTO ZUSCHLAGSSÄTZE" not in source

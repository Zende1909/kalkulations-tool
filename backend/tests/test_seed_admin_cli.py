"""AP3: Admin-Seed nur per CLI, nicht im App-Startup."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as app_main
from app.core.security import verify_password
from app.models.user import User
from app.scripts import seed_admin as seed_admin_mod
from app.scripts.seed_admin import main as seed_admin_main
from app.scripts.seed_admin import seed_admin_user


def test_main_lifespan_source_has_no_admin_seed():
    source = Path(app_main.__file__).read_text(encoding="utf-8")
    assert "seed_admin_user" not in source
    assert "seed_admin" not in source


def test_production_startup_does_not_call_admin_seed(monkeypatch: pytest.MonkeyPatch):
    from tests.test_security_hardening import _patch_startup_to_skip_db

    _patch_startup_to_skip_db(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "production", raising=False)
    monkeypatch.setattr(
        app_main.settings,
        "JWT_SECRET_KEY",
        "super-strong-production-secret-!@#42",
        raising=False,
    )
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_SEED_ENABLED", True, raising=False)

    with TestClient(app_main.app) as client:
        assert client.get("/health").status_code == 200
    assert not hasattr(app_main, "seed_admin_user")


def _sqlite_user_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    User.__table__.create(bind=engine, checkfirst=True)
    return Session()


def test_cli_rejects_when_seed_not_enabled(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setattr(seed_admin_mod.settings, "LOCAL_ADMIN_SEED_ENABLED", False, raising=False)
    assert seed_admin_main([]) == 1
    err = capsys.readouterr().err
    assert "LOCAL_ADMIN_SEED_ENABLED" in err


def test_cli_rejects_non_local_database(monkeypatch: pytest.MonkeyPatch, capsys):
    monkeypatch.setattr(seed_admin_mod.settings, "LOCAL_ADMIN_SEED_ENABLED", True, raising=False)
    monkeypatch.setattr(
        seed_admin_mod.settings,
        "DATABASE_URL",
        "postgresql+psycopg2://u:p@db.example.com:5432/prod",
        raising=False,
    )
    monkeypatch.setattr(seed_admin_mod.settings, "LOCAL_ADMIN_EMAIL", "a@b.c", raising=False)
    monkeypatch.setattr(seed_admin_mod.settings, "LOCAL_ADMIN_PASSWORD", "secret", raising=False)

    monkeypatch.setattr(
        "app.database.SessionLocal",
        lambda: SimpleNamespace(close=lambda: None),
    )

    assert seed_admin_main([]) == 1
    err = capsys.readouterr().err.lower()
    assert "fehlgeschlagen" in err
    assert "local" in err


def test_cli_seed_success_and_idempotent(monkeypatch: pytest.MonkeyPatch, capsys):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    User.__table__.create(bind=engine, checkfirst=True)

    monkeypatch.setattr(seed_admin_mod.settings, "LOCAL_ADMIN_SEED_ENABLED", True, raising=False)
    monkeypatch.setattr(seed_admin_mod.settings, "DATABASE_URL", "sqlite://", raising=False)
    monkeypatch.setattr(
        seed_admin_mod.settings, "LOCAL_ADMIN_EMAIL", "cli-admin@example.com", raising=False
    )
    monkeypatch.setattr(
        seed_admin_mod.settings, "LOCAL_ADMIN_PASSWORD", "cli-secret-password", raising=False
    )
    # main() closes each session; factory must return a fresh one per call.
    monkeypatch.setattr("app.database.SessionLocal", Session)

    assert seed_admin_main([]) == 0
    assert "created" in capsys.readouterr().out

    with Session() as db:
        user = db.query(User).filter(User.email == "cli-admin@example.com").one()
        assert user.role == "admin"
        assert verify_password("cli-secret-password", user.hashed_password)
        before_hash = user.hashed_password

    assert seed_admin_main([]) == 0
    assert "skipped" in capsys.readouterr().out

    with Session() as db:
        user = db.query(User).filter(User.email == "cli-admin@example.com").one()
        assert user.hashed_password == before_hash
        assert db.query(User).count() == 1


def test_seed_admin_user_noop_when_disabled(monkeypatch: pytest.MonkeyPatch):
    db = _sqlite_user_session()
    monkeypatch.setattr(seed_admin_mod.settings, "LOCAL_ADMIN_SEED_ENABLED", False, raising=False)
    assert seed_admin_user(db) is None
    assert db.query(User).count() == 0
    db.close()

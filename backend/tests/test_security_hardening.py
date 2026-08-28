from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.main as app_main
from app.config import DEFAULT_JWT_SECRET_KEY
from app.core.security import verify_password
from app.scripts.seed_admin import seed_admin_user
from app.database import Base
from app.models.user import User


@contextmanager
def _dummy_engine_connection():
    class _DummyResult:
        def scalar(self) -> int:
            return 1

    class _DummyConnection:
        def execute(self, *_args, **_kwargs) -> _DummyResult:
            return _DummyResult()

    yield _DummyConnection()


def _patch_startup_to_skip_db(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_main, "verify_database_connection", lambda: None)
    monkeypatch.setattr(app_main, "ensure_spritzguss_schema", lambda _engine: None)
    monkeypatch.setattr(app_main, "ensure_spritzguss_hierarchy_schema", lambda _engine: None)
    monkeypatch.setattr(app_main, "ensure_investition_schema", lambda _engine: None)
    monkeypatch.setattr(app_main, "ensure_investition_assignment_schema", lambda _engine: None)
    monkeypatch.setattr(app_main, "ensure_assembly_structure_schema", lambda _engine: None)
    monkeypatch.setattr(app_main, "ensure_kaufteil_sga_override_schema", lambda _engine: None)
    monkeypatch.setattr(app_main, "verify_database_at_alembic_head", lambda _engine: None)

    # Avoid any actual schema create calls in tests.
    monkeypatch.setattr(app_main.Base.metadata, "create_all", lambda *args, **kwargs: None)

    # Avoid /health depending on a live DB.
    monkeypatch.setattr(app_main.engine, "connect", lambda: _dummy_engine_connection())


def test_startup_rejects_default_jwt_secret_in_production(monkeypatch: pytest.MonkeyPatch):
    _patch_startup_to_skip_db(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "production", raising=False)
    monkeypatch.setattr(app_main.settings, "JWT_SECRET_KEY", DEFAULT_JWT_SECRET_KEY, raising=False)

    with pytest.raises(RuntimeError) as exc:
        with TestClient(app_main.app):
            pass
    assert "JWT_SECRET_KEY" in str(exc.value)
    assert DEFAULT_JWT_SECRET_KEY not in str(exc.value)


@pytest.mark.parametrize("jwt_secret", ["", "   "])
def test_startup_rejects_empty_whitespace_jwt_secret_in_production(
    monkeypatch: pytest.MonkeyPatch,
    jwt_secret: str,
):
    _patch_startup_to_skip_db(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "production", raising=False)
    monkeypatch.setattr(app_main.settings, "JWT_SECRET_KEY", jwt_secret, raising=False)

    with pytest.raises(RuntimeError):
        with TestClient(app_main.app):
            pass


def test_startup_allows_default_jwt_secret_in_development(monkeypatch: pytest.MonkeyPatch):
    _patch_startup_to_skip_db(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "development", raising=False)
    monkeypatch.setattr(app_main.settings, "JWT_SECRET_KEY", DEFAULT_JWT_SECRET_KEY, raising=False)

    with TestClient(app_main.app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"status", "service", "database"}
        assert body["status"] in {"ok", "unavailable"}


def test_healthcheck_does_not_expose_internal_db_details(monkeypatch: pytest.MonkeyPatch):
    _patch_startup_to_skip_db(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "development", raising=False)

    with TestClient(app_main.app) as client:
        resp = client.get("/health")
        body = resp.json()

    assert "database_url" not in body
    assert "postgres" not in str(body).lower()
    assert "user" not in str(body).lower()
    assert "host" not in str(body).lower()


def test_cors_allows_local_frontend_origin(monkeypatch: pytest.MonkeyPatch):
    _patch_startup_to_skip_db(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "development", raising=False)

    with TestClient(app_main.app) as client:
        resp = client.get("/health", headers={"Origin": "http://localhost:5173"})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
        assert "access-control-allow-credentials" not in resp.headers


def test_cors_denies_unauthorized_origin(monkeypatch: pytest.MonkeyPatch):
    _patch_startup_to_skip_db(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "development", raising=False)

    with TestClient(app_main.app) as client:
        resp = client.get("/health", headers={"Origin": "http://evil.example"})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") is None


def test_admin_seed_requires_explicit_local_activation(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    # Creating the whole ORM schema would fail on SQLite due to unsupported JSONB.
    User.__table__.create(bind=engine, checkfirst=True)

    # Ensure the seed is NOT enabled: no user should be created.
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_SEED_ENABLED", False, raising=False)
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_EMAIL", "local-admin@example.com", raising=False)
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_PASSWORD", "pw", raising=False)
    monkeypatch.setattr(app_main.settings, "DATABASE_URL", "sqlite://", raising=False)

    seed_admin_user(db)
    assert db.query(User).count() == 0

    # Enable seed but keep missing credentials -> must fail fast.
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_SEED_ENABLED", True, raising=False)
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_EMAIL", None, raising=False)
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_PASSWORD", None, raising=False)
    with pytest.raises(RuntimeError):
        seed_admin_user(db)

    # Enable seed with explicit credentials -> user is created.
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_EMAIL", "local-admin@example.com", raising=False)
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_PASSWORD", "secret-password", raising=False)
    seed_admin_user(db)

    user = db.query(User).filter(User.email == "local-admin@example.com").first()
    assert user is not None
    assert user.role == "admin"
    assert verify_password("secret-password", user.hashed_password)

    # Existing user must not be modified.
    before_hash = user.hashed_password
    seed_admin_user(db)
    user = db.query(User).filter(User.email == "local-admin@example.com").first()
    assert user.hashed_password == before_hash

    db.close()


def test_startup_accepts_strong_jwt_secret_in_production(monkeypatch: pytest.MonkeyPatch):
    _patch_startup_to_skip_db(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "production", raising=False)
    monkeypatch.setattr(app_main.settings, "JWT_SECRET_KEY", "super-strong-production-secret-!@#42", raising=False)

    with TestClient(app_main.app) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        assert set(resp.json().keys()) == {"status", "service", "database"}


def test_cors_preflight_allows_authorization_header(monkeypatch: pytest.MonkeyPatch):
    _patch_startup_to_skip_db(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "development", raising=False)

    origin = "http://localhost:5173"
    with TestClient(app_main.app) as client:
        resp = client.options(
            "/health",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

    assert resp.status_code < 400
    assert resp.headers.get("access-control-allow-origin") == origin

    allow_headers = resp.headers.get("access-control-allow-headers", "").lower()
    assert "authorization" in allow_headers
    assert "access-control-allow-credentials" not in resp.headers


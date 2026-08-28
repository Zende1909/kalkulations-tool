"""AP2: Startup entkoppelt von Schema-Bootstrap / Alembic-Validierung."""

from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

import app.main as app_main
from app.config import Settings
from app.startup import (
    get_alembic_head_revisions,
    verify_database_at_alembic_head,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
SMOKE_DB = "kalkulation_alembic_ap2_smoke"
APP_DB = "kalkulationstool"
ADMIN_DSN = "dbname=postgres user=postgres password=admin123 host=localhost port=5432"
BASE_URL = "postgresql+psycopg2://postgres:admin123@localhost:5432"


@contextmanager
def _dummy_engine_connection():
    class _DummyResult:
        def scalar(self) -> int:
            return 1

    class _DummyConnection:
        def execute(self, *_args, **_kwargs) -> _DummyResult:
            return _DummyResult()

    yield _DummyConnection()


def _patch_common(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Shared stubs; returns call counters for bootstrap side effects."""
    calls = {
        "create_all": 0,
        "ensure_spritzguss": 0,
        "ensure_hierarchy": 0,
        "ensure_investition": 0,
        "ensure_assembly": 0,
        "alembic_verify": 0,
    }

    monkeypatch.setattr(app_main, "verify_database_connection", lambda: None)
    monkeypatch.setattr(
        app_main.Base.metadata,
        "create_all",
        lambda *a, **k: calls.__setitem__("create_all", calls["create_all"] + 1),
    )
    monkeypatch.setattr(
        app_main,
        "ensure_spritzguss_schema",
        lambda _e: calls.__setitem__("ensure_spritzguss", calls["ensure_spritzguss"] + 1),
    )
    monkeypatch.setattr(
        app_main,
        "ensure_spritzguss_hierarchy_schema",
        lambda _e: calls.__setitem__("ensure_hierarchy", calls["ensure_hierarchy"] + 1),
    )
    monkeypatch.setattr(
        app_main,
        "ensure_investition_schema",
        lambda _e: calls.__setitem__("ensure_investition", calls["ensure_investition"] + 1),
    )
    monkeypatch.setattr(
        app_main,
        "ensure_assembly_structure_schema",
        lambda _e: calls.__setitem__("ensure_assembly", calls["ensure_assembly"] + 1),
    )
    monkeypatch.setattr(
        app_main,
        "verify_database_at_alembic_head",
        lambda _e: calls.__setitem__("alembic_verify", calls["alembic_verify"] + 1),
    )
    monkeypatch.setattr(app_main.engine, "connect", lambda: _dummy_engine_connection())
    return calls


def test_production_disables_schema_bootstrap_hard():
    s = Settings(
        APP_ENV="production",
        ALLOW_STARTUP_SCHEMA_BOOTSTRAP=True,
        JWT_SECRET_KEY="prod-secret-not-default",
    )
    assert s.startup_schema_bootstrap_enabled is False


def test_development_bootstrap_default_on():
    s = Settings(APP_ENV="development", ALLOW_STARTUP_SCHEMA_BOOTSTRAP=None)
    assert s.startup_schema_bootstrap_enabled is True


def test_development_bootstrap_can_be_disabled():
    s = Settings(APP_ENV="development", ALLOW_STARTUP_SCHEMA_BOOTSTRAP=False)
    assert s.startup_schema_bootstrap_enabled is False


def test_production_startup_skips_create_all_and_ensure(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_common(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "production", raising=False)
    monkeypatch.setattr(app_main.settings, "ALLOW_STARTUP_SCHEMA_BOOTSTRAP", None, raising=False)
    monkeypatch.setattr(
        app_main.settings,
        "JWT_SECRET_KEY",
        "super-strong-production-secret-!@#42",
        raising=False,
    )

    with TestClient(app_main.app) as client:
        assert client.get("/health").status_code == 200

    assert calls["create_all"] == 0
    assert calls["ensure_spritzguss"] == 0
    assert calls["ensure_hierarchy"] == 0
    assert calls["ensure_investition"] == 0
    assert calls["ensure_assembly"] == 0
    assert calls["alembic_verify"] == 1
    assert not hasattr(app_main, "seed_admin_user")


def test_production_startup_does_not_mutate_via_bootstrap(monkeypatch: pytest.MonkeyPatch):
    """Production path must not invoke any bootstrap mutation entry points."""
    calls = _patch_common(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "production", raising=False)
    monkeypatch.setattr(
        app_main.settings,
        "JWT_SECRET_KEY",
        "super-strong-production-secret-!@#42",
        raising=False,
    )
    # Even if seed flags were wrongly enabled, startup must not seed.
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_SEED_ENABLED", True, raising=False)

    with TestClient(app_main.app):
        pass

    mutation_calls = (
        calls["create_all"]
        + calls["ensure_spritzguss"]
        + calls["ensure_hierarchy"]
        + calls["ensure_investition"]
        + calls["ensure_assembly"]
    )
    assert mutation_calls == 0
    assert not hasattr(app_main, "seed_admin_user")


def test_development_startup_runs_bootstrap_without_admin_seed(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_common(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "development", raising=False)
    monkeypatch.setattr(app_main.settings, "ALLOW_STARTUP_SCHEMA_BOOTSTRAP", None, raising=False)
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_SEED_ENABLED", True, raising=False)

    with TestClient(app_main.app) as client:
        assert client.get("/health").status_code == 200

    assert calls["create_all"] == 1
    assert calls["ensure_spritzguss"] == 1
    assert calls["ensure_hierarchy"] == 1
    assert calls["ensure_investition"] == 1
    assert calls["ensure_assembly"] == 1
    assert calls["alembic_verify"] == 0
    assert not hasattr(app_main, "seed_admin_user")


def test_test_env_startup_runs_bootstrap_without_admin_seed(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_common(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "test", raising=False)
    monkeypatch.setattr(app_main.settings, "ALLOW_STARTUP_SCHEMA_BOOTSTRAP", None, raising=False)
    monkeypatch.setattr(app_main.settings, "LOCAL_ADMIN_SEED_ENABLED", True, raising=False)

    with TestClient(app_main.app):
        pass

    assert calls["create_all"] == 1
    assert not hasattr(app_main, "seed_admin_user")


def test_development_can_disable_bootstrap_and_validate_alembic(monkeypatch: pytest.MonkeyPatch):
    calls = _patch_common(monkeypatch)
    monkeypatch.setattr(app_main.settings, "APP_ENV", "development", raising=False)
    monkeypatch.setattr(app_main.settings, "ALLOW_STARTUP_SCHEMA_BOOTSTRAP", False, raising=False)

    with TestClient(app_main.app):
        pass

    assert calls["create_all"] == 0
    assert calls["alembic_verify"] == 1


def test_ensure_investition_schema_contains_no_dml():
    import inspect

    from app.db_upgrade import ensure_investition_schema

    source = inspect.getsource(ensure_investition_schema)
    upper = source.upper()
    assert "UPDATE " not in upper
    assert "INSERT " not in upper
    assert "DELETE FROM" not in upper

    module_source = Path(__import__("app.db_upgrade", fromlist=["db_upgrade"]).__file__).read_text(
        encoding="utf-8"
    )
    assert "except Exception:\n                pass" not in module_source
    assert "except Exception:\n                    pass" not in module_source


def test_alembic_head_revision_is_plant_costing():
    heads = get_alembic_head_revisions()
    assert heads == ("e1a0011_kaufteil_sga_override",)


def test_warn_if_database_behind_alembic_head_logs(caplog, tmp_path: Path):
    from app.startup import warn_if_database_behind_alembic_head

    engine = create_engine(f"sqlite:///{tmp_path / 'behind.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(64) NOT NULL)"))
        conn.execute(
            text(
                "INSERT INTO alembic_version (version_num) "
                "VALUES ('e1a0006_spritzguss_material_nominierung')"
            )
        )
    with caplog.at_level("WARNING"):
        warn_if_database_behind_alembic_head(engine)
    assert any("hinter dem Code-Head" in r.message for r in caplog.records)


def test_verify_alembic_head_fails_when_unversioned(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite:///:memory:")
    with pytest.raises(RuntimeError, match="nicht Alembic-versioniert"):
        verify_database_at_alembic_head(engine)


def test_verify_alembic_head_fails_on_wrong_revision(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'wrong.db'}")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('not_the_head')"))
    with pytest.raises(RuntimeError, match="weicht vom erwarteten Head ab"):
        verify_database_at_alembic_head(engine)


def _postgres_available() -> bool:
    try:
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

        conn = psycopg2.connect(ADMIN_DSN)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        conn.close()
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available for smoke DB")
def test_smoke_production_startup_against_temp_migrated_db(monkeypatch: pytest.MonkeyPatch):
    """Create disposable DB, alembic upgrade, validate production startup path, drop DB.

    Does not touch the working DB kalkulationstool.
    """
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    def admin():
        c = psycopg2.connect(ADMIN_DSN)
        c.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return c

    # Snapshot working DB (read-only)
    with psycopg2.connect(
        f"dbname={APP_DB} user=postgres password=admin123 host=localhost port=5432"
    ) as app_conn:
        with app_conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='alembic_version')"
            )
            app_had_alembic = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_type='BASE TABLE'"
            )
            app_tables_before = cur.fetchone()[0]
            inv_count_before = None
            inv_status_fingerprint = None
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='investitionen')"
            )
            if cur.fetchone()[0]:
                cur.execute("SELECT count(*) FROM investitionen")
                inv_count_before = cur.fetchone()[0]
                cur.execute(
                    "SELECT coalesce(sum(hashtext(status::text)), 0), "
                    "coalesce(sum(hashtext(coalesce(name, ''))), 0) FROM investitionen"
                )
                inv_status_fingerprint = cur.fetchone()

    c = admin()
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (SMOKE_DB,),
        )
        cur.execute(f'DROP DATABASE IF EXISTS "{SMOKE_DB}"')
        cur.execute(f'CREATE DATABASE "{SMOKE_DB}"')
        cur.close()
    finally:
        c.close()

    env = os.environ.copy()
    env["DATABASE_URL"] = f"{BASE_URL}/{SMOKE_DB}"
    up = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert up.returncode == 0, up.stdout + up.stderr

    smoke_engine = create_engine(f"{BASE_URL}/{SMOKE_DB}")
    try:
        verify_database_at_alembic_head(smoke_engine)

        # Lifespan production path against smoke engine
        monkeypatch.setattr(app_main, "verify_database_connection", lambda: None)
        monkeypatch.setattr(app_main, "engine", smoke_engine)
        monkeypatch.setattr(app_main.settings, "APP_ENV", "production", raising=False)
        monkeypatch.setattr(
            app_main.settings,
            "JWT_SECRET_KEY",
            "super-strong-production-secret-!@#42",
            raising=False,
        )
        create_all_calls = {"n": 0}
        monkeypatch.setattr(
            app_main.Base.metadata,
            "create_all",
            lambda *a, **k: create_all_calls.__setitem__("n", create_all_calls["n"] + 1),
        )
        ensure_calls = {"n": 0}

        def _count_ensure(_e):
            ensure_calls["n"] += 1

        monkeypatch.setattr(app_main, "ensure_spritzguss_schema", _count_ensure)
        monkeypatch.setattr(app_main, "ensure_spritzguss_hierarchy_schema", _count_ensure)
        monkeypatch.setattr(app_main, "ensure_investition_schema", _count_ensure)
        monkeypatch.setattr(app_main, "ensure_assembly_structure_schema", _count_ensure)

        with TestClient(app_main.app) as client:
            assert client.get("/health").status_code == 200

        assert create_all_calls["n"] == 0
        assert ensure_calls["n"] == 0

        # Empty DB must fail Alembic check
        empty_name = f"{SMOKE_DB}_empty"
        c = admin()
        try:
            cur = c.cursor()
            cur.execute(f'DROP DATABASE IF EXISTS "{empty_name}"')
            cur.execute(f'CREATE DATABASE "{empty_name}"')
            cur.close()
        finally:
            c.close()
        empty_engine = create_engine(f"{BASE_URL}/{empty_name}")
        with pytest.raises(RuntimeError, match="nicht Alembic-versioniert"):
            verify_database_at_alembic_head(empty_engine)
        empty_engine.dispose()
        c = admin()
        try:
            cur = c.cursor()
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (empty_name,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{empty_name}"')
            cur.close()
        finally:
            c.close()
    finally:
        smoke_engine.dispose()
        c = admin()
        try:
            cur = c.cursor()
            cur.execute(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = %s AND pid <> pg_backend_pid()",
                (SMOKE_DB,),
            )
            cur.execute(f'DROP DATABASE IF EXISTS "{SMOKE_DB}"')
            cur.close()
        finally:
            c.close()

    # Working DB untouched
    with psycopg2.connect(
        f"dbname={APP_DB} user=postgres password=admin123 host=localhost port=5432"
    ) as app_conn:
        with app_conn.cursor() as cur:
            cur.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema='public' AND table_name='alembic_version')"
            )
            assert cur.fetchone()[0] == app_had_alembic
            cur.execute(
                "SELECT count(*) FROM information_schema.tables "
                "WHERE table_schema='public' AND table_type='BASE TABLE'"
            )
            assert cur.fetchone()[0] == app_tables_before
            if inv_count_before is not None:
                cur.execute("SELECT count(*) FROM investitionen")
                assert cur.fetchone()[0] == inv_count_before
                cur.execute(
                    "SELECT coalesce(sum(hashtext(status::text)), 0), "
                    "coalesce(sum(hashtext(coalesce(name, ''))), 0) FROM investitionen"
                )
                assert cur.fetchone() == inv_status_fingerprint

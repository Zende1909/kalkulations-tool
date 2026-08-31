"""AP3 M-1: baugruppen.project_id-Backfill (nur temporäre Smoke-DB)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
SMOKE_DB = "kalkulation_alembic_ap3_m1_smoke"
APP_DB = "kalkulationstool"
ADMIN_DSN = "dbname=postgres user=postgres password=admin123 host=localhost port=5432"
BASE_URL = "postgresql+psycopg2://postgres:admin123@localhost:5432"
REVISION = "e1a0003_m1_baugruppe_project_backfill"
PREV_HEAD = "e1a0002_investition_legacy_data"
MIGRATION_FILE = BACKEND_DIR / "alembic" / "versions" / "e1a0003_m1_baugruppe_project_backfill.py"


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


def _admin():
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    conn = psycopg2.connect(ADMIN_DSN)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    return conn


def _drop_db(name: str) -> None:
    c = _admin()
    try:
        cur = c.cursor()
        cur.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
            "WHERE datname = %s AND pid <> pg_backend_pid()",
            (name,),
        )
        cur.execute(f'DROP DATABASE IF EXISTS "{name}"')
        cur.close()
    finally:
        c.close()


def _create_db(name: str) -> None:
    c = _admin()
    try:
        cur = c.cursor()
        cur.execute(f'CREATE DATABASE "{name}"')
        cur.close()
    finally:
        c.close()


def _alembic(env: dict, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _load_migration_module():
    spec = importlib.util.spec_from_file_location(
        "e1a0003_m1_baugruppe_project_backfill",
        MIGRATION_FILE,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_m1_revision_module_contract():
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert 'revision: str = "e1a0003_m1_baugruppe_project_backfill"' in source
    assert 'down_revision' in source and PREV_HEAD in source
    assert "SET project_id = linked_project_id" in source
    assert "WHERE project_id IS NULL" in source
    assert "EXISTS" in source and "projects" in source
    assert "Rollback-Dokumentation" in source
    assert "op.create_table" not in source
    assert "op.drop_table" not in source
    assert "op.add_column" not in source
    assert "ALTER TABLE baugruppen" not in source
    assert "alembic_version" in source  # version_num widen only
    assert "baugruppe_spritzguss" not in source
    assert "baugruppe_kaufteil" not in source
    assert "baugruppe_veredelung" not in source
    assert "legacy_mode" in source  # documented as unchanged


def test_m1_revision_is_in_chain_before_m5():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    scripts = ScriptDirectory.from_config(cfg)
    assert scripts.get_heads() == ["e1a0017_simplify_cycle_time"]
    rev = scripts.get_revision(REVISION)
    assert rev is not None
    assert rev.down_revision == PREV_HEAD


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available for smoke DB")
def test_m1_project_backfill_cases_and_idempotency_on_smoke_db():
    """Cases: successful backfill, keep set project_id, skip invalid FK, idempotent."""
    import psycopg2

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
            cur.execute(
                "SELECT coalesce(sum(hashtext(coalesce(project_id::text, ''))), 0), "
                "coalesce(sum(hashtext(coalesce(linked_project_id::text, ''))), 0), "
                "coalesce(sum(hashtext(coalesce(legacy_mode::text, ''))), 0), "
                "coalesce(sum(hashtext(coalesce(projekt, ''))), 0) "
                "FROM baugruppen"
            )
            bg_fp_before = cur.fetchone()

    _drop_db(SMOKE_DB)
    _create_db(SMOKE_DB)
    env = os.environ.copy()
    env["DATABASE_URL"] = f"{BASE_URL}/{SMOKE_DB}"

    try:
        up_prev = _alembic(env, "upgrade", PREV_HEAD)
        assert up_prev.returncode == 0, up_prev.stdout + up_prev.stderr

        engine = create_engine(f"{BASE_URL}/{SMOKE_DB}")
        with engine.begin() as conn:
            # Minimal customer/program/project for valid FK targets
            conn.execute(
                text(
                    """
                    INSERT INTO customers (
                        id, customer_number, name, notes, active, created_at, updated_at
                    ) VALUES (
                        1, 'C-1', 'Kunde', '', TRUE, NOW(), NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO programs (
                        id, customer_id, program_number, name, vehicle_series,
                        status, production_plant, notes, active, created_at, updated_at
                    ) VALUES (
                        1, 1, 'PRG-1', 'Programm', '',
                        'Anfrage', '', '', TRUE, NOW(), NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO projects (
                        id, program_id, project_number, name, component_area,
                        quantity_per_vehicle, status, notes, active,
                        created_at, updated_at
                    ) VALUES
                    (10, 1, 'P-10', 'Projekt 10', '', 1.0, 'Anfrage', '', TRUE, NOW(), NOW()),
                    (20, 1, 'P-20', 'Projekt 20', '', 1.0, 'Anfrage', '', TRUE, NOW(), NOW())
                    """
                )
            )
            # Temporarily allow orphan linked_project_id for the invalid-FK case
            conn.execute(
                text(
                    "ALTER TABLE baugruppen DROP CONSTRAINT IF EXISTS "
                    "baugruppen_linked_project_id_fkey"
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO baugruppen (
                        name, teilenummer, kunde, projekt, jahresstueckzahl,
                        beschreibung, status, aktiv, linked_project_id, project_id,
                        assembly_type, structure_version, legacy_mode, pricing_status,
                        created_at, updated_at
                    ) VALUES
                    -- 1) successful backfill: project_id NULL, valid linked
                    ('BG Backfill', 'BG-1', 'K', 'Freitext bleibt', 0,
                     '', 'entwurf', TRUE, 10, NULL,
                     'TOP_LEVEL', 1, TRUE, 'NOT_APPLICABLE', NOW(), NOW()),
                    -- 2) already set project_id must stay (even if linked differs)
                    ('BG Keep', 'BG-2', 'K', 'anderes', 0,
                     '', 'entwurf', TRUE, 10, 20,
                     'TOP_LEVEL', 1, FALSE, 'NOT_APPLICABLE', NOW(), NOW()),
                    -- 3) invalid linked_project_id -> skip (project_id stays NULL)
                    ('BG Invalid', 'BG-3', 'K', 'x', 0,
                     '', 'entwurf', TRUE, 99999, NULL,
                     'TOP_LEVEL', 1, TRUE, 'NOT_APPLICABLE', NOW(), NOW()),
                    -- 4) both NULL -> no change
                    ('BG None', 'BG-4', 'K', 'y', 0,
                     '', 'entwurf', TRUE, NULL, NULL,
                     'TOP_LEVEL', 1, TRUE, 'NOT_APPLICABLE', NOW(), NOW())
                    """
                )
            )
            # Count legacy junction rows before (must stay 0 / unchanged)
            legacy_before = conn.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM baugruppe_spritzguss_zuordnungen) + "
                    "(SELECT count(*) FROM baugruppe_kaufteil_zuordnungen) + "
                    "(SELECT count(*) FROM baugruppe_veredelung_zuordnungen)"
                )
            ).scalar()

        up_m1 = _alembic(env, "upgrade", REVISION)
        assert up_m1.returncode == 0, up_m1.stdout + up_m1.stderr

        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            rows = {
                r.teilenummer: (
                    r.project_id,
                    r.linked_project_id,
                    r.legacy_mode,
                    r.projekt,
                )
                for r in conn.execute(
                    text(
                        "SELECT teilenummer, project_id, linked_project_id, "
                        "legacy_mode, projekt FROM baugruppen ORDER BY teilenummer"
                    )
                )
            }
            legacy_after = conn.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM baugruppe_spritzguss_zuordnungen) + "
                    "(SELECT count(*) FROM baugruppe_kaufteil_zuordnungen) + "
                    "(SELECT count(*) FROM baugruppe_veredelung_zuordnungen)"
                )
            ).scalar()

        assert version == REVISION
        assert rows["BG-1"] == (10, 10, True, "Freitext bleibt")
        assert rows["BG-2"] == (20, 10, False, "anderes")
        assert rows["BG-3"] == (None, 99999, True, "x")
        assert rows["BG-4"] == (None, None, True, "y")
        assert legacy_after == legacy_before == 0

        # Idempotency: run upgrade() twice more in-process
        module = _load_migration_module()
        with engine.begin() as conn:
            before = list(
                conn.execute(
                    text(
                        "SELECT id, project_id, linked_project_id, legacy_mode, projekt "
                        "FROM baugruppen ORDER BY id"
                    )
                ).fetchall()
            )
            context = MigrationContext.configure(conn)
            with Operations.context(context):
                module.upgrade()
                module.upgrade()
            after = list(
                conn.execute(
                    text(
                        "SELECT id, project_id, linked_project_id, legacy_mode, projekt "
                        "FROM baugruppen ORDER BY id"
                    )
                ).fetchall()
            )
        assert before == after

        engine.dispose()
    finally:
        _drop_db(SMOKE_DB)

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
            cur.execute(
                "SELECT coalesce(sum(hashtext(coalesce(project_id::text, ''))), 0), "
                "coalesce(sum(hashtext(coalesce(linked_project_id::text, ''))), 0), "
                "coalesce(sum(hashtext(coalesce(legacy_mode::text, ''))), 0), "
                "coalesce(sum(hashtext(coalesce(projekt, ''))), 0) "
                "FROM baugruppen"
            )
            assert cur.fetchone() == bg_fp_before

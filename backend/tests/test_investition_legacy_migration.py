"""AP3 Teil 1: Investitions-Datenmigration (nur temporäre Smoke-DB)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parents[1]
SMOKE_DB = "kalkulation_alembic_ap3_invest_smoke"
APP_DB = "kalkulationstool"
ADMIN_DSN = "dbname=postgres user=postgres password=admin123 host=localhost port=5432"
BASE_URL = "postgresql+psycopg2://postgres:admin123@localhost:5432"
REVISION = "e1a0002_investition_legacy_data"
BASELINE = "e1a0001_baseline"


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


def test_investition_legacy_migration_module_contract():
    path = BACKEND_DIR / "alembic" / "versions" / "e1a0002_investition_legacy_data.py"
    source = path.read_text(encoding="utf-8")
    assert 'revision: str = "e1a0002_investition_legacy_data"' in source
    assert 'down_revision' in source and "e1a0001_baseline" in source
    assert "WHERE name IS NULL OR name = ''" in source
    assert "WHERE status = 'offen'" in source
    assert "Rollback-Dokumentation" in source
    assert "status = 'offen'" in source  # docs mention manual status rollback
    # No schema DDL in this data migration
    assert "op.create_table" not in source
    assert "op.drop_table" not in source


def test_db_upgrade_investition_has_no_legacy_dml():
    from app.db_upgrade import ensure_investition_schema
    import inspect

    source = inspect.getsource(ensure_investition_schema)
    upper = source.upper()
    assert "UPDATE " not in upper
    assert "STATUS = 'OFFEN'" not in upper
    assert "STATUS = 'IN PLANUNG'" not in upper


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available for smoke DB")
def test_investition_legacy_data_migration_and_idempotency_on_smoke_db():
    """Runs alembic data migration only on a disposable smoke database."""
    import importlib.util

    import psycopg2

    # Read-only fingerprint of working DB (must stay unchanged)
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
            cur.execute("SELECT count(*) FROM investitionen")
            inv_before = cur.fetchone()[0]
            cur.execute(
                "SELECT coalesce(sum(hashtext(status::text)), 0), "
                "coalesce(sum(hashtext(coalesce(name, ''))), 0) FROM investitionen"
            )
            inv_fp_before = cur.fetchone()

    _drop_db(SMOKE_DB)
    _create_db(SMOKE_DB)
    env = os.environ.copy()
    env["DATABASE_URL"] = f"{BASE_URL}/{SMOKE_DB}"

    try:
        up_base = _alembic(env, "upgrade", BASELINE)
        assert up_base.returncode == 0, up_base.stdout + up_base.stderr

        engine = create_engine(f"{BASE_URL}/{SMOKE_DB}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO investitionen (
                        name, investment_type, payment_type, amount,
                        amortization_volume, cost_per_piece, project_id, customer,
                        part_name, part_number, supplier, status, description,
                        included_in_unit_price, archived, created_at, updated_at
                    ) VALUES
                    ('', 'Werkzeug', 'Einmalzahlung', 1,
                     NULL, NULL, 'P1', 'C1',
                     'Teil A', '', '', 'offen', '',
                     FALSE, FALSE, NOW(), NOW()),
                    ('', 'Werkzeug', 'Einmalzahlung', 1,
                     NULL, NULL, 'P1', 'C1',
                     '', '', '', 'offen', 'Beschreibung B',
                     FALSE, FALSE, NOW(), NOW()),
                    ('', 'Werkzeug', 'Einmalzahlung', 1,
                     NULL, NULL, 'P1', 'C1',
                     '', '', '', 'offen', '',
                     FALSE, FALSE, NOW(), NOW()),
                    ('Bereits gesetzt', 'Werkzeug', 'Einmalzahlung', 1,
                     NULL, NULL, 'P1', 'C1',
                     'Ignorieren', '', '', 'In Planung', 'Ignorieren',
                     FALSE, FALSE, NOW(), NOW()),
                    ('Fester Name', 'Werkzeug', 'Einmalzahlung', 1,
                     NULL, NULL, 'P1', 'C1',
                     'X', '', '', 'offen', 'Y',
                     FALSE, FALSE, NOW(), NOW())
                    """
                )
            )

        up_head = _alembic(env, "upgrade", "head")
        assert up_head.returncode == 0, up_head.stdout + up_head.stderr

        with engine.connect() as conn:
            rows = {
                r.id: (r.name, r.status, r.part_name, r.description)
                for r in conn.execute(
                    text(
                        "SELECT id, name, status, part_name, description "
                        "FROM investitionen ORDER BY id"
                    )
                )
            }
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()

        assert version == REVISION
        assert len(rows) == 5
        values = list(rows.values())
        assert values[0][0] == "Teil A" and values[0][1] == "In Planung"
        assert values[1][0] == "Beschreibung B" and values[1][1] == "In Planung"
        assert values[2][0] == "Investition" and values[2][1] == "In Planung"
        assert values[3][0] == "Bereits gesetzt" and values[3][1] == "In Planung"
        assert values[4][0] == "Fester Name" and values[4][1] == "In Planung"

        # Idempotency: run upgrade() again in-process (already at head)
        spec = importlib.util.spec_from_file_location(
            "e1a0002_investition_legacy_data",
            BACKEND_DIR / "alembic" / "versions" / "e1a0002_investition_legacy_data.py",
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        with engine.begin() as conn:
            before = list(
                conn.execute(
                    text("SELECT id, name, status FROM investitionen ORDER BY id")
                ).fetchall()
            )
            context = MigrationContext.configure(conn)
            with Operations.context(context):
                module.upgrade()
                module.upgrade()
            after = list(
                conn.execute(
                    text("SELECT id, name, status FROM investitionen ORDER BY id")
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
            cur.execute("SELECT count(*) FROM investitionen")
            assert cur.fetchone()[0] == inv_before
            cur.execute(
                "SELECT coalesce(sum(hashtext(status::text)), 0), "
                "coalesce(sum(hashtext(coalesce(name, ''))), 0) FROM investitionen"
            )
            assert cur.fetchone() == inv_fp_before

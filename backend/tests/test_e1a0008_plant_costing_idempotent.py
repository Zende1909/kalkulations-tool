"""Idempotente e1a0008_plant_costing: Frisch-DB, Bootstrap-DB, Wiederholung."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
REVISION = "e1a0008_plant_costing"
PREV = "e1a0007_veredelung_snapshot_yield"

BASE_URL = "postgresql+psycopg2://postgres:admin123@localhost:5432"
ADMIN_DSN = "dbname=postgres user=postgres password=admin123 host=localhost port=5432"
SMOKE_FRESH = "kalkulation_e1a0008_fresh_smoke"
SMOKE_BOOT = "kalkulation_e1a0008_boot_smoke"

MASCHINEN_PLANT_COLS = [
    "werk_id",
    "maschinentyp",
    "variante",
    "source_currency",
    "arbeitstage_pro_jahr",
    "schichten_pro_tag",
    "stunden_pro_schicht",
    "oee",
    "investment",
    "flaeche_sqm",
    "space_cost_satz_pro_sqm_jahr",
    "abschreibungsdauer_jahre",
    "zinssatz",
    "versicherungssatz",
    "instandhaltungssatz",
    "stromverbrauch_kwh_h",
    "strompreis",
    "druckluftverbrauch_m3_h",
    "druckluftpreis",
    "kuehlwasserverbrauch_m3_h",
    "kuehlwasserpreis",
    "setup_zeit_min",
    "setup_mitarbeiter",
    "jahresstunden",
    "space_costs_pro_stunde",
    "abschreibung_pro_stunde",
    "zinsen_pro_stunde",
    "versicherung_pro_stunde",
    "instandhaltung_pro_stunde",
    "energie_pro_stunde",
    "stundensatz_source",
    "rate_updated_at",
]


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
    _drop_db(name)
    c = _admin()
    try:
        cur = c.cursor()
        cur.execute(f'CREATE DATABASE "{name}"')
        cur.close()
    finally:
        c.close()


def _alembic_upgrade(db_name: str, revision: str = "head") -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"{BASE_URL}/{db_name}"
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", revision],
        cwd=str(BACKEND_DIR),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_e1a0008_upgrade(engine: Engine) -> None:
    """Führt upgrade() der Revision im Alembic-Operations-Kontext aus."""
    import importlib.util

    path = BACKEND_DIR / "alembic" / "versions" / "e1a0008_plant_costing.py"
    spec = importlib.util.spec_from_file_location("e1a0008_plant_costing", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with engine.begin() as conn:
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            mod.upgrade()


def _assert_plant_structure(engine: Engine) -> None:
    insp = inspect(engine)
    for t in (
        "laender",
        "werke",
        "werk_zuschlaege",
        "maschinen",
        "lohnkosten",
        "spritzguss_kalkulationen",
        "baugruppen",
    ):
        assert insp.has_table(t), t

    mcols = {c["name"] for c in insp.get_columns("maschinen")}
    for col in MASCHINEN_PLANT_COLS:
        assert col in mcols, col

    lcols = {c["name"] for c in insp.get_columns("lohnkosten")}
    for col in ("werk_id", "rolle", "source_currency", "source_rate"):
        assert col in lcols, col
    rolle = next(c for c in insp.get_columns("lohnkosten") if c["name"] == "rolle")
    assert rolle["nullable"] is False

    sg = {c["name"] for c in insp.get_columns("spritzguss_kalkulationen")}
    assert "werk_id" in sg and "losgroesse" in sg
    bg = {c["name"] for c in insp.get_columns("baugruppen")}
    assert "werk_id" in bg

    def has_fk(table: str, cols: list[str], ref: str) -> bool:
        for fk in insp.get_foreign_keys(table):
            if (
                list(fk.get("constrained_columns") or []) == cols
                and fk.get("referred_table") == ref
            ):
                return True
        return False

    assert has_fk("werke", ["land_id"], "laender")
    assert has_fk("werk_zuschlaege", ["werk_id"], "werke")
    assert has_fk("maschinen", ["werk_id"], "werke")
    assert has_fk("lohnkosten", ["werk_id"], "werke")
    assert has_fk("spritzguss_kalkulationen", ["werk_id"], "werke")
    assert has_fk("baugruppen", ["werk_id"], "werke")


def _stamp_revision(engine: Engine, revision: str) -> None:
    """Stamp ohne alembic CLI (version_num oft VARCHAR(32) bei Default-Create)."""
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version ("
                "version_num VARCHAR(64) NOT NULL PRIMARY KEY)"
            )
        )
        conn.execute(text("DELETE FROM alembic_version"))
        conn.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:v)"),
            {"v": revision},
        )


def _create_pre_plant_skeleton(engine: Engine) -> None:
    """Minimale Tabellen wie vor e1a0008 plus Bootstrap-Plant-Tabellen."""
    stmts = [
        """
        CREATE TABLE maschinen (
            id SERIAL PRIMARY KEY,
            bezeichnung VARCHAR(255) NOT NULL,
            maschinen_nr VARCHAR(50) NOT NULL UNIQUE,
            stundensatz DOUBLE PRECISION NOT NULL,
            schliesskraft_t DOUBLE PRECISION NOT NULL DEFAULT 0,
            aktiv BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE lohnkosten (
            id SERIAL PRIMARY KEY,
            bezeichnung VARCHAR(255) NOT NULL,
            kosten_pro_stunde DOUBLE PRECISION NOT NULL,
            kostenstelle VARCHAR(50) NOT NULL DEFAULT '',
            gueltig_ab DATE NOT NULL,
            aktiv BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE spritzguss_kalkulationen (
            id SERIAL PRIMARY KEY,
            teilebezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE baugruppen (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) NOT NULL DEFAULT '',
            aktiv BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """,
        """
        CREATE TABLE laender (
            id SERIAL PRIMARY KEY,
            code VARCHAR(16) NOT NULL,
            name VARCHAR(255) NOT NULL,
            aktiv BOOLEAN NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """,
        "CREATE UNIQUE INDEX ix_laender_code ON laender (code)",
        "CREATE INDEX ix_laender_id ON laender (id)",
        """
        CREATE TABLE werke (
            id SERIAL PRIMARY KEY,
            land_id INTEGER NOT NULL REFERENCES laender(id) ON DELETE RESTRICT,
            code VARCHAR(32) NOT NULL,
            name VARCHAR(255) NOT NULL,
            currency VARCHAR(8) NOT NULL,
            fx_to_eur DOUBLE PRECISION NOT NULL,
            aktiv BOOLEAN NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
        """,
        "CREATE UNIQUE INDEX ix_werke_code ON werke (code)",
        "CREATE INDEX ix_werke_land_id ON werke (land_id)",
        "CREATE INDEX ix_werke_id ON werke (id)",
        """
        CREATE TABLE werk_zuschlaege (
            id SERIAL PRIMARY KEY,
            werk_id INTEGER NOT NULL REFERENCES werke(id) ON DELETE CASCADE,
            typ VARCHAR(64) NOT NULL,
            bezeichnung VARCHAR(255) NOT NULL,
            satz_prozent DOUBLE PRECISION NOT NULL,
            kostenbasis VARCHAR(64) NOT NULL,
            aktiv BOOLEAN NOT NULL,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            CONSTRAINT uq_werk_zuschlag_werk_typ UNIQUE (werk_id, typ)
        )
        """,
        "CREATE INDEX ix_werk_zuschlaege_werk_id ON werk_zuschlaege (werk_id)",
        "CREATE INDEX ix_werk_zuschlaege_typ ON werk_zuschlaege (typ)",
    ]
    with engine.begin() as conn:
        for stmt in stmts:
            conn.execute(text(stmt))


def test_e1a0008_source_has_no_seeds_or_dml():
    source = (
        BACKEND_DIR / "alembic" / "versions" / "e1a0008_plant_costing.py"
    ).read_text(encoding="utf-8")
    upper = source.upper()
    assert "INSERT INTO" not in upper
    assert "UPDATE " not in upper
    assert "DELETE FROM" not in upper
    assert "seed" not in source.lower() or "keine" in source.lower()


def test_alembic_head_is_e1a0009_after_werk_params():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    heads = ScriptDirectory.from_config(cfg).get_heads()
    assert heads == ["e1a0011_kaufteil_sga_override"]
    rev = ScriptDirectory.from_config(cfg).get_revision(REVISION)
    assert rev is not None
    assert rev.down_revision == PREV


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_e1a0008_fresh_database_full_chain():
    _create_db(SMOKE_FRESH)
    engine = create_engine(f"{BASE_URL}/{SMOKE_FRESH}")
    try:
        up = _alembic_upgrade(SMOKE_FRESH, REVISION)
        assert up.returncode == 0, up.stdout + up.stderr
        with engine.connect() as conn:
            ver = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert ver == REVISION
        _assert_plant_structure(engine)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM laender")).scalar() == 0
            assert conn.execute(text("SELECT COUNT(*) FROM werke")).scalar() == 0
            assert conn.execute(text("SELECT COUNT(*) FROM werk_zuschlaege")).scalar() == 0
        _run_e1a0008_upgrade(engine)
        _assert_plant_structure(engine)
        with engine.connect() as conn:
            assert (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                == REVISION
            )
    finally:
        engine.dispose()
        _drop_db(SMOKE_FRESH)


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_e1a0008_bootstrap_existing_plant_tables_and_missing_columns():
    _create_db(SMOKE_BOOT)
    engine = create_engine(f"{BASE_URL}/{SMOKE_BOOT}")
    try:
        _create_pre_plant_skeleton(engine)
        now = datetime.now(timezone.utc)
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO lohnkosten "
                    "(bezeichnung, kosten_pro_stunde, kostenstelle, gueltig_ab, aktiv, "
                    "created_at, updated_at) VALUES "
                    "('Alt', 10.0, 'X', :d, TRUE, :c, :u)"
                ),
                {"d": date(2024, 1, 1), "c": now, "u": now},
            )
            conn.execute(
                text(
                    "INSERT INTO maschinen "
                    "(bezeichnung, maschinen_nr, stundensatz, schliesskraft_t, aktiv, "
                    "created_at, updated_at) VALUES "
                    "('M1', 'M-1', 100.0, 50.0, TRUE, :c, :u)"
                ),
                {"c": now, "u": now},
            )
        _stamp_revision(engine, PREV)

        insp = inspect(engine)
        assert insp.has_table("laender")
        assert "werk_id" not in {c["name"] for c in insp.get_columns("maschinen")}
        assert "rolle" not in {c["name"] for c in insp.get_columns("lohnkosten")}
        boot_fk_werke = {f.get("name") for f in insp.get_foreign_keys("werke")}
        boot_fk_zuschlag = {
            f.get("name") for f in insp.get_foreign_keys("werk_zuschlaege")
        }

        up = _alembic_upgrade(SMOKE_BOOT, REVISION)
        assert up.returncode == 0, up.stdout + up.stderr

        with engine.connect() as conn:
            assert (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                == REVISION
            )
            assert conn.execute(text("SELECT COUNT(*) FROM lohnkosten")).scalar() == 1
            assert conn.execute(text("SELECT COUNT(*) FROM maschinen")).scalar() == 1
            assert conn.execute(text("SELECT rolle FROM lohnkosten")).scalar() == "sonstig"

        _assert_plant_structure(engine)

        insp2 = inspect(engine)
        werke_fks = insp2.get_foreign_keys("werke")
        assert len(werke_fks) == 1
        assert werke_fks[0].get("name") in boot_fk_werke
        z_fks = insp2.get_foreign_keys("werk_zuschlaege")
        assert len(z_fks) == 1
        assert z_fks[0].get("name") in boot_fk_zuschlag

        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO lohnkosten "
                    "(bezeichnung, kosten_pro_stunde, kostenstelle, gueltig_ab, aktiv, "
                    "rolle, created_at, updated_at) VALUES "
                    "('Neu', 12.0, 'Y', :d, TRUE, 'produktion', :c, :u)"
                ),
                {"d": date(2025, 1, 1), "c": now, "u": now},
            )
            rows = conn.execute(
                text("SELECT bezeichnung, rolle FROM lohnkosten ORDER BY id")
            ).all()
        assert rows == [("Alt", "sonstig"), ("Neu", "produktion")]

        _run_e1a0008_upgrade(engine)
        _run_e1a0008_upgrade(engine)
        _assert_plant_structure(engine)
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM lohnkosten")).scalar() == 2
            assert conn.execute(text("SELECT COUNT(*) FROM maschinen")).scalar() == 1
    finally:
        engine.dispose()
        _drop_db(SMOKE_BOOT)


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available")
def test_e1a0008_rerun_after_simulated_duplicate_table_state():
    """Nach fehlgeschlagenem create_table(laender): Tabellen da, Revision noch e1a0007."""
    name = "kalkulation_e1a0008_dup_smoke"
    _create_db(name)
    engine = create_engine(f"{BASE_URL}/{name}")
    try:
        _create_pre_plant_skeleton(engine)
        _stamp_revision(engine, PREV)
        up = _alembic_upgrade(name, REVISION)
        assert up.returncode == 0, up.stdout + up.stderr
        with engine.connect() as conn:
            assert (
                conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
                == REVISION
            )
        _assert_plant_structure(engine)
    finally:
        engine.dispose()
        _drop_db(name)

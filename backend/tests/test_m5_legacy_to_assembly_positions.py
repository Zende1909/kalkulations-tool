"""AP3 M-5: Legacy -> assembly_positions (nur temporäre Smoke-DB)."""

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
SMOKE_DB = "kalkulation_alembic_ap3_m5_smoke"
APP_DB = "kalkulationstool"
ADMIN_DSN = "dbname=postgres user=postgres password=admin123 host=localhost port=5432"
BASE_URL = "postgresql+psycopg2://postgres:admin123@localhost:5432"
REVISION = "e1a0004_m5_assembly_positions"
PREV = "e1a0003_m1_baugruppe_project_backfill"
MIGRATION_FILE = BACKEND_DIR / "alembic" / "versions" / "e1a0004_m5_assembly_positions.py"


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


def test_m5_revision_module_contract():
    source = MIGRATION_FILE.read_text(encoding="utf-8")
    assert len(REVISION) <= 32
    assert f'revision: str = "{REVISION}"' in source
    assert PREV in source
    assert "PART" in source and "PURCHASED_PART" in source and "PROCESS" in source
    assert "Keine SUBASSEMBLY" in source
    assert "'SUBASSEMBLY'" not in source
    assert "baugruppe_spritzguss_zuordnungen" in source
    assert "baugruppe_kaufteil_zuordnungen" in source
    assert "baugruppe_veredelung_zuordnungen" in source
    assert "DELETE FROM" not in source.upper()
    assert "DROP TABLE" not in source.upper()
    assert "legacy_mode" in source  # documented as unchanged
    assert "Rollback-Dokumentation" in source
    assert "pauschale" in source.lower() or "keine" in source.lower()


def test_m5_is_in_alembic_chain_before_head():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    scripts = ScriptDirectory.from_config(cfg)
    assert scripts.get_heads() == ["e1a0011_kaufteil_sga_override"]
    rev = scripts.get_revision(REVISION)
    assert rev is not None
    assert rev.down_revision == PREV
    e8 = scripts.get_revision("e1a0008_plant_costing")
    assert e8 is not None
    assert e8.down_revision == "e1a0007_veredelung_snapshot_yield"
    e9 = scripts.get_revision("e1a0009_werk_operating_params")
    assert e9 is not None
    assert e9.down_revision == "e1a0008_plant_costing"


@pytest.mark.skipif(not _postgres_available(), reason="PostgreSQL not available for smoke DB")
def test_m5_legacy_mapping_snapshots_sequences_idempotency_on_smoke_db():
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
                "SELECT coalesce(sum(hashtext(coalesce(project_id::text,''))),0), "
                "coalesce(sum(hashtext(coalesce(legacy_mode::text,''))),0) FROM baugruppen"
            )
            bg_fp_before = cur.fetchone()
            cur.execute(
                "SELECT "
                "(SELECT count(*) FROM baugruppe_spritzguss_zuordnungen),"
                "(SELECT count(*) FROM baugruppe_kaufteil_zuordnungen),"
                "(SELECT count(*) FROM baugruppe_veredelung_zuordnungen),"
                "(SELECT count(*) FROM assembly_positions)"
            )
            legacy_fp_before = cur.fetchone()

    _drop_db(SMOKE_DB)
    _create_db(SMOKE_DB)
    env = os.environ.copy()
    env["DATABASE_URL"] = f"{BASE_URL}/{SMOKE_DB}"

    try:
        # Full chain through previous head, then seed, then upgrade to M-5
        up_prev = _alembic(env, "upgrade", PREV)
        assert up_prev.returncode == 0, up_prev.stdout + up_prev.stderr

        engine = create_engine(f"{BASE_URL}/{SMOKE_DB}")
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO customers (
                        id, customer_number, name, notes, active, created_at, updated_at
                    ) VALUES (1, 'C1', 'Kunde', '', TRUE, NOW(), NOW())
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
                        1, 1, 'PRG1', 'Prog', '', 'Anfrage', '', '', TRUE, NOW(), NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO projects (
                        id, program_id, project_number, name, component_area,
                        quantity_per_vehicle, status, notes, active, created_at, updated_at
                    ) VALUES (
                        10, 1, 'P10', 'Projekt', '', 1.0, 'Anfrage', '', TRUE, NOW(), NOW()
                    )
                    """
                )
            )
            # Minimal spritzguss / kaufteil / veredelung
            conn.execute(
                text(
                    """
                    INSERT INTO spritzguss_kalkulationen (
                        id, teilebezeichnung, teilenummer, kunde, projekt, jahresstueckzahl,
                        schussgewicht_g, teilegewicht_netto_g, ausschussquote_pct,
                        materialpreis_pro_kg, zykluszeit_s, kavitaeten, maschinenstundensatz,
                        lohnstundensatz, werkzeug_abrechnungsart, werkzeugkosten_eur,
                        mgk_pct, fgk_pct, vvgk_pct, gewinn_pct, skonto_pct,
                        notizen, aktiv, created_at, updated_at
                    ) VALUES (
                        501, 'Teil', 'T-501', '', '', 0,
                        0, 0, 0, 0, 0, 1, 0, 0, 'amortisation', 0,
                        0, 0, 0, 0, 0, '', TRUE, NOW(), NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO kaufteile (
                        id, artikelnummer, bezeichnung, beschreibung, lieferant,
                        einheit, preis, waehrung, aktiv, created_at, updated_at
                    ) VALUES (
                        301, 'KT-301', 'Kaufteil', '', 'Lieferant X',
                        'Stk', 1.5, 'EUR', TRUE, NOW(), NOW()
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO veredelungsschritte (
                        id, bezeichnung, veredelungsart, reihenfolge, beschreibung,
                        taktzeit_s, anzahl_mitarbeiter, lohnstundensatz,
                        verbrauchskosten_je_stueck, ausschussquote_pct, fgk_pct,
                        aktiv, created_at, updated_at
                    ) VALUES (
                        401, 'Schweißen', 'Montage', 1, '',
                        0, 1, 0, 0, 0, 0, TRUE, NOW(), NOW()
                    )
                    """
                )
            )
            # BG-A: eligible with mixed legacy (test sequence tiebreaker)
            # reihenfolge: Kaufteil=1, Spritzguss=1 (PART before PURCHASED at same reihenfolge),
            # Veredelung=2
            conn.execute(
                text(
                    """
                    INSERT INTO baugruppen (
                        id, name, teilenummer, kunde, projekt, jahresstueckzahl,
                        beschreibung, status, aktiv, project_id, linked_project_id,
                        assembly_type, structure_version, legacy_mode, pricing_status,
                        created_at, updated_at
                    ) VALUES
                    (100, 'Migrieren', 'BG-A', '', '', 0, '', 'entwurf', TRUE, 10, 10,
                     'TOP_LEVEL', 1, TRUE, 'NOT_APPLICABLE', NOW(), NOW()),
                    -- no project_id -> skip
                    (101, 'Ohne Projekt', 'BG-B', '', '', 0, '', 'entwurf', TRUE, NULL, NULL,
                     'TOP_LEVEL', 1, TRUE, 'NOT_APPLICABLE', NOW(), NOW()),
                    -- already has positions -> skip
                    (102, 'Bereits Positionen', 'BG-C', '', '', 0, '', 'entwurf', TRUE, 10, 10,
                     'TOP_LEVEL', 1, FALSE, 'NOT_APPLICABLE', NOW(), NOW())
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO baugruppe_spritzguss_zuordnungen (
                        baugruppe_id, spritzguss_kalkulation_id, menge, reihenfolge,
                        snapshot_preis, snapshot_bezeichnung, snapshot_teilenummer,
                        created_at, updated_at
                    ) VALUES
                    (100, 501, 2.0, 1, 12.5, 'Snap Teil', 'T-501', NOW(), NOW()),
                    (101, 501, 1.0, 1, 1.0, 'Skip', 'T', NOW(), NOW())
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO baugruppe_kaufteil_zuordnungen (
                        baugruppe_id, kaufteil_id, menge, reihenfolge,
                        snapshot_preis, snapshot_bezeichnung, snapshot_lieferant,
                        created_at, updated_at
                    ) VALUES
                    (100, 301, 3.0, 1, 9.9, 'Snap KT', 'Lieferant X', NOW(), NOW())
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO baugruppe_veredelung_zuordnungen (
                        baugruppe_id, veredelungsschritt_id, reihenfolge, mengenfaktor,
                        snapshot_kosten, snapshot_bezeichnung, created_at, updated_at
                    ) VALUES
                    (100, 401, 2, 1.5, 4.4, 'Snap Proc', NOW(), NOW())
                    """
                )
            )
            # Pre-existing position on BG-C (blocks migration for that BG)
            conn.execute(
                text(
                    """
                    INSERT INTO assembly_positions (
                        parent_assembly_id, position_type, sequence, quantity,
                        quantity_factor, price_basis, active, part_calculation_id,
                        purchased_part_id, child_assembly_id, finishing_step_id,
                        name_snapshot, part_number_snapshot, supplier_snapshot,
                        created_at, updated_at
                    ) VALUES (
                        102, 'PART', 1, 1.0, 1.0, 'COST', TRUE, 501,
                        NULL, NULL, NULL, 'existing', '', '', NOW(), NOW()
                    )
                    """
                )
            )
            legacy_counts_before = conn.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM baugruppe_spritzguss_zuordnungen),"
                    "(SELECT count(*) FROM baugruppe_kaufteil_zuordnungen),"
                    "(SELECT count(*) FROM baugruppe_veredelung_zuordnungen)"
                )
            ).fetchone()
            legacy_mode_before = {
                r.teilenummer: r.legacy_mode
                for r in conn.execute(
                    text("SELECT teilenummer, legacy_mode FROM baugruppen")
                )
            }

        up = _alembic(env, "upgrade", REVISION)
        assert up.returncode == 0, up.stdout + up.stderr

        with engine.connect() as conn:
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
            assert version == REVISION

            rows = list(
                conn.execute(
                    text(
                        """
                        SELECT parent_assembly_id, position_type, sequence, quantity,
                               quantity_factor, price_basis, part_calculation_id,
                               purchased_part_id, finishing_step_id, child_assembly_id,
                               price_snapshot, cost_snapshot, name_snapshot,
                               part_number_snapshot, supplier_snapshot
                        FROM assembly_positions
                        ORDER BY parent_assembly_id, sequence
                        """
                    )
                ).mappings()
            )

            # BG-A (100): 3 positions; BG-C keeps 1 existing; BG-B none
            by_parent: dict[int, list] = {}
            for r in rows:
                by_parent.setdefault(r["parent_assembly_id"], []).append(r)

            assert set(by_parent) == {100, 102}
            assert len(by_parent[100]) == 3
            assert len(by_parent[102]) == 1
            assert by_parent[102][0]["name_snapshot"] == "existing"

            # Sequence: same reihenfolge 1 -> PART before PURCHASED_PART, then PROCESS reihenfolge 2
            p0, p1, p2 = by_parent[100]
            assert p0["sequence"] == 1 and p0["position_type"] == "PART"
            assert p0["part_calculation_id"] == 501
            assert p0["quantity"] == 2.0
            assert p0["quantity_factor"] == 1.0
            assert p0["price_basis"] == "COST"
            assert p0["price_snapshot"] == 12.5
            assert p0["name_snapshot"] == "Snap Teil"
            assert p0["part_number_snapshot"] == "T-501"
            assert p0["purchased_part_id"] is None
            assert p0["finishing_step_id"] is None
            assert p0["child_assembly_id"] is None

            assert p1["sequence"] == 2 and p1["position_type"] == "PURCHASED_PART"
            assert p1["purchased_part_id"] == 301
            assert p1["quantity"] == 3.0
            assert p1["price_basis"] is None
            assert p1["price_snapshot"] == 9.9
            assert p1["name_snapshot"] == "Snap KT"
            assert p1["supplier_snapshot"] == "Lieferant X"
            assert p1["part_calculation_id"] is None

            assert p2["sequence"] == 3 and p2["position_type"] == "PROCESS"
            assert p2["finishing_step_id"] == 401
            assert p2["quantity"] == 1.0
            assert p2["quantity_factor"] == 1.5
            assert p2["price_basis"] is None
            assert p2["cost_snapshot"] == 4.4
            assert p2["name_snapshot"] == "Snap Proc"
            assert p2["part_calculation_id"] is None
            assert p2["purchased_part_id"] is None

            # No SUBASSEMBLY
            assert all(r["position_type"] != "SUBASSEMBLY" for r in rows)

            legacy_counts_after = conn.execute(
                text(
                    "SELECT "
                    "(SELECT count(*) FROM baugruppe_spritzguss_zuordnungen),"
                    "(SELECT count(*) FROM baugruppe_kaufteil_zuordnungen),"
                    "(SELECT count(*) FROM baugruppe_veredelung_zuordnungen)"
                )
            ).fetchone()
            assert legacy_counts_after == legacy_counts_before

            legacy_mode_after = {
                r.teilenummer: r.legacy_mode
                for r in conn.execute(
                    text("SELECT teilenummer, legacy_mode FROM baugruppen")
                )
            }
            assert legacy_mode_after == legacy_mode_before

        # Idempotency
        spec = importlib.util.spec_from_file_location(
            "e1a0004_m5_assembly_positions", MIGRATION_FILE
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with engine.begin() as conn:
            before = list(
                conn.execute(
                    text(
                        "SELECT id, parent_assembly_id, position_type, sequence "
                        "FROM assembly_positions ORDER BY id"
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
                        "SELECT id, parent_assembly_id, position_type, sequence "
                        "FROM assembly_positions ORDER BY id"
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
                "SELECT coalesce(sum(hashtext(coalesce(project_id::text,''))),0), "
                "coalesce(sum(hashtext(coalesce(legacy_mode::text,''))),0) FROM baugruppen"
            )
            assert cur.fetchone() == bg_fp_before
            cur.execute(
                "SELECT "
                "(SELECT count(*) FROM baugruppe_spritzguss_zuordnungen),"
                "(SELECT count(*) FROM baugruppe_kaufteil_zuordnungen),"
                "(SELECT count(*) FROM baugruppe_veredelung_zuordnungen),"
                "(SELECT count(*) FROM assembly_positions)"
            )
            assert cur.fetchone() == legacy_fp_before

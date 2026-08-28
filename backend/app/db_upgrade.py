"""Leichte Schema-Upgrades für bestehende PostgreSQL-Tabellen (Dev-/Test-Bootstrap).

Nur DDL. Keine DML (kein UPDATE/INSERT/DELETE von Geschäftsdaten).
Wird ausschließlich über den kontrollierten Startup-Bootstrap-Pfad
(ALLOW_STARTUP_SCHEMA_BOOTSTRAP / APP_ENV=development|test) aufgerufen –
niemals im Produktionsstart.
"""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


def _execute_ddl(engine: Engine, statements: list[str], *, label: str) -> None:
    """Execute DDL statements; log failures. PostgreSQL: re-raise. SQLite: warn+skip.

    SQLite is only used in unit tests; these helpers target PostgreSQL production DDL.
    """
    with engine.begin() as conn:
        for stmt in statements:
            preview = " ".join(stmt.split())[:180]
            try:
                conn.execute(text(stmt))
                logger.debug("%s: OK – %s", label, preview)
            except SQLAlchemyError:
                if engine.dialect.name == "sqlite":
                    logger.warning(
                        "%s: SQLite überspringt Statement (Dev-Test-Pfad, kein Prod-Ziel): %s",
                        label,
                        preview,
                        exc_info=True,
                    )
                    continue
                logger.exception("%s: DDL fehlgeschlagen – %s", label, preview)
                raise


def ensure_spritzguss_schema(engine: Engine) -> None:
    statements = [
        """
        ALTER TABLE spritzguss_kalkulationen
        ADD COLUMN IF NOT EXISTS werkzeug_abrechnungsart VARCHAR(32)
        NOT NULL DEFAULT 'amortisation'
        """,
        """
        ALTER TABLE spritzguss_kalkulationen
        ALTER COLUMN amortisationsvolumen DROP NOT NULL
        """,
        """
        ALTER TABLE spritzguss_kalkulationen
        ALTER COLUMN amortisationsvolumen TYPE INTEGER
        USING ROUND(amortisationsvolumen)::INTEGER
        """,
    ]
    _execute_ddl(engine, statements, label="ensure_spritzguss_schema")


def ensure_spritzguss_hierarchy_schema(engine: Engine) -> None:
    statements = [
        """
        ALTER TABLE spritzguss_kalkulationen
        ADD COLUMN IF NOT EXISTS customer_id INTEGER
        REFERENCES customers(id) ON DELETE SET NULL
        """,
        """
        ALTER TABLE spritzguss_kalkulationen
        ADD COLUMN IF NOT EXISTS program_id INTEGER
        REFERENCES programs(id) ON DELETE SET NULL
        """,
        """
        ALTER TABLE spritzguss_kalkulationen
        ADD COLUMN IF NOT EXISTS project_id INTEGER
        REFERENCES projects(id) ON DELETE SET NULL
        """,
        """
        ALTER TABLE spritzguss_kalkulationen
        ADD COLUMN IF NOT EXISTS calculation_year INTEGER
        """,
        """
        ALTER TABLE spritzguss_kalkulationen
        ADD COLUMN IF NOT EXISTS project_volume DOUBLE PRECISION
        """,
        """
        ALTER TABLE investitionen
        ADD COLUMN IF NOT EXISTS linked_project_id INTEGER
        REFERENCES projects(id) ON DELETE SET NULL
        """,
        """
        ALTER TABLE baugruppen
        ADD COLUMN IF NOT EXISTS linked_project_id INTEGER
        REFERENCES projects(id) ON DELETE SET NULL
        """,
    ]
    _execute_ddl(engine, statements, label="ensure_spritzguss_hierarchy_schema")


def ensure_investition_schema(engine: Engine) -> None:
    """Additive Investitions-Spalten (DDL only – keine Status-/Name-Updates)."""
    statements = [
        """
        ALTER TABLE investitionen
        ADD COLUMN IF NOT EXISTS baugruppe_id INTEGER
        REFERENCES baugruppen(id) ON DELETE SET NULL
        """,
        "ALTER TABLE investitionen ADD COLUMN IF NOT EXISTS name VARCHAR(255) NOT NULL DEFAULT ''",
        "ALTER TABLE investitionen ADD COLUMN IF NOT EXISTS customer VARCHAR(255) NOT NULL DEFAULT ''",
        "ALTER TABLE investitionen ADD COLUMN IF NOT EXISTS part_number VARCHAR(255) NOT NULL DEFAULT ''",
        "ALTER TABLE investitionen ADD COLUMN IF NOT EXISTS amortization_volume INTEGER",
        "ALTER TABLE investitionen ADD COLUMN IF NOT EXISTS cost_per_piece DOUBLE PRECISION",
        "ALTER TABLE investitionen ADD COLUMN IF NOT EXISTS supplier VARCHAR(255) NOT NULL DEFAULT ''",
        "ALTER TABLE investitionen ADD COLUMN IF NOT EXISTS order_date DATE",
        "ALTER TABLE investitionen ADD COLUMN IF NOT EXISTS delivery_date DATE",
        """
        ALTER TABLE investitionen
        ADD COLUMN IF NOT EXISTS included_in_unit_price BOOLEAN NOT NULL DEFAULT FALSE
        """,
        """
        ALTER TABLE investitionen
        ADD COLUMN IF NOT EXISTS archived BOOLEAN NOT NULL DEFAULT FALSE
        """,
    ]
    _execute_ddl(engine, statements, label="ensure_investition_schema")


def ensure_assembly_structure_schema(engine: Engine) -> None:
    """Phase A: assembly_positions + erweiterte baugruppen-Spalten (additiv).

    Manuelle Migrationsschritte (NICHT automatisch ausführen):
    - M-1: project_id aus linked_project_id backfillen (nur nach Freigabe)
    - M-5: Legacy-Zuordnungen nach assembly_positions kopieren (nur nach Freigabe)
    """
    statements = [
        """
        ALTER TABLE baugruppen
        ADD COLUMN IF NOT EXISTS project_id INTEGER
        REFERENCES projects(id) ON DELETE RESTRICT
        """,
        """
        ALTER TABLE baugruppen
        ADD COLUMN IF NOT EXISTS assembly_type VARCHAR(16) NOT NULL DEFAULT 'TOP_LEVEL'
        """,
        """
        ALTER TABLE baugruppen
        ADD COLUMN IF NOT EXISTS structure_version INTEGER NOT NULL DEFAULT 1
        """,
        """
        ALTER TABLE baugruppen
        ADD COLUMN IF NOT EXISTS legacy_mode BOOLEAN NOT NULL DEFAULT TRUE
        """,
        """
        ALTER TABLE baugruppen
        ADD COLUMN IF NOT EXISTS snapshots_captured_at TIMESTAMPTZ
        """,
        """
        ALTER TABLE baugruppen
        ADD COLUMN IF NOT EXISTS pricing_status VARCHAR(32) NOT NULL DEFAULT 'NOT_APPLICABLE'
        """,
        """
        CREATE TABLE IF NOT EXISTS assembly_positions (
            id SERIAL PRIMARY KEY,
            parent_assembly_id INTEGER NOT NULL
                REFERENCES baugruppen(id) ON DELETE CASCADE,
            position_type VARCHAR(32) NOT NULL,
            sequence INTEGER NOT NULL,
            quantity DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            quantity_factor DOUBLE PRECISION NOT NULL DEFAULT 1.0,
            price_basis VARCHAR(16),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            label VARCHAR(255),
            part_calculation_id INTEGER
                REFERENCES spritzguss_kalkulationen(id) ON DELETE RESTRICT,
            purchased_part_id INTEGER
                REFERENCES kaufteile(id) ON DELETE RESTRICT,
            child_assembly_id INTEGER
                REFERENCES baugruppen(id) ON DELETE RESTRICT,
            finishing_step_id INTEGER
                REFERENCES veredelungsschritte(id) ON DELETE RESTRICT,
            cost_snapshot DOUBLE PRECISION,
            price_snapshot DOUBLE PRECISION,
            name_snapshot VARCHAR(255) NOT NULL DEFAULT '',
            part_number_snapshot VARCHAR(100) NOT NULL DEFAULT '',
            supplier_snapshot VARCHAR(255) NOT NULL DEFAULT '',
            snapshots_captured_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_ap_position_type
                CHECK (position_type IN ('PART', 'PURCHASED_PART', 'SUBASSEMBLY', 'PROCESS')),
            CONSTRAINT chk_ap_price_basis
                CHECK (price_basis IS NULL OR price_basis IN ('COST', 'SELF_COST', 'SALES_PRICE')),
            CONSTRAINT chk_ap_sequence_positive CHECK (sequence >= 1),
            CONSTRAINT chk_ap_quantity_positive CHECK (quantity > 0),
            CONSTRAINT chk_ap_quantity_factor_positive CHECK (quantity_factor > 0),
            CONSTRAINT chk_ap_part_refs CHECK (
                position_type <> 'PART'
                OR (
                    part_calculation_id IS NOT NULL
                    AND purchased_part_id IS NULL
                    AND child_assembly_id IS NULL
                    AND finishing_step_id IS NULL
                    AND price_basis IS NOT NULL
                )
            ),
            CONSTRAINT chk_ap_purchased_refs CHECK (
                position_type <> 'PURCHASED_PART'
                OR (
                    purchased_part_id IS NOT NULL
                    AND part_calculation_id IS NULL
                    AND child_assembly_id IS NULL
                    AND finishing_step_id IS NULL
                    AND price_basis IS NULL
                )
            ),
            CONSTRAINT chk_ap_subassembly_refs CHECK (
                position_type <> 'SUBASSEMBLY'
                OR (
                    child_assembly_id IS NOT NULL
                    AND part_calculation_id IS NULL
                    AND purchased_part_id IS NULL
                    AND finishing_step_id IS NULL
                    AND price_basis IS NOT NULL
                )
            ),
            CONSTRAINT chk_ap_process_refs CHECK (
                position_type <> 'PROCESS'
                OR (
                    finishing_step_id IS NOT NULL
                    AND part_calculation_id IS NULL
                    AND purchased_part_id IS NULL
                    AND child_assembly_id IS NULL
                    AND price_basis IS NULL
                )
            )
        )
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_ap_parent_sequence
            ON assembly_positions (parent_assembly_id, sequence)
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_ap_parent_part
            ON assembly_positions (parent_assembly_id, part_calculation_id)
            WHERE position_type = 'PART'
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_ap_parent_assembly
            ON assembly_positions (parent_assembly_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_ap_child_assembly
            ON assembly_positions (child_assembly_id)
            WHERE child_assembly_id IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_ap_part_calculation
            ON assembly_positions (part_calculation_id)
            WHERE part_calculation_id IS NOT NULL
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_baugruppen_project_id
            ON baugruppen (project_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_baugruppen_assembly_type
            ON baugruppen (assembly_type)
        """,
    ]
    constraint_statements = [
        """
        DO $$
        BEGIN
            ALTER TABLE baugruppen
            ADD CONSTRAINT chk_baugruppen_assembly_type
            CHECK (assembly_type IN ('TOP_LEVEL', 'SUBASSEMBLY'));
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
        """,
        """
        DO $$
        BEGIN
            ALTER TABLE baugruppen
            ADD CONSTRAINT chk_baugruppen_pricing_status
            CHECK (pricing_status IN ('NOT_APPLICABLE', 'CALCULATED', 'STALE'));
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$
        """,
    ]
    _execute_ddl(engine, statements, label="ensure_assembly_structure_schema")
    if engine.dialect.name == "postgresql":
        _execute_ddl(
            engine,
            constraint_statements,
            label="ensure_assembly_structure_schema.constraints",
        )


def ensure_kaufteil_sga_override_schema(engine: Engine) -> None:
    """SG&A-Override-Spalten auf kaufteile (Migration e1a0011, idempotent)."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    if not insp.has_table("kaufteile"):
        return
    statements = [
        """
        ALTER TABLE kaufteile
        ADD COLUMN IF NOT EXISTS sga_override_aktiv BOOLEAN NOT NULL DEFAULT FALSE
        """,
        """
        ALTER TABLE kaufteile
        ADD COLUMN IF NOT EXISTS sga_satz_manuell DOUBLE PRECISION
        """,
    ]
    _execute_ddl(engine, statements, label="ensure_kaufteil_sga_override_schema")

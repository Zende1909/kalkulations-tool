"""Leichte Schema-Upgrades für bestehende PostgreSQL-Tabellen (ohne Alembic)."""

from sqlalchemy import text
from sqlalchemy.engine import Engine


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
    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception:
                # Tabelle existiert ggf. noch nicht – create_all legt sie neu an.
                pass


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
    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass


def ensure_investition_schema(engine: Engine) -> None:
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
        """
        UPDATE investitionen
        SET name = COALESCE(NULLIF(name, ''), NULLIF(part_name, ''), NULLIF(description, ''), 'Investition')
        WHERE name IS NULL OR name = ''
        """,
        """
        UPDATE investitionen
        SET status = 'In Planung'
        WHERE status = 'offen'
        """,
    ]
    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass

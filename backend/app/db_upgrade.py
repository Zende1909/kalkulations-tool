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


def ensure_investition_schema(engine: Engine) -> None:
    statements = [
        """
        ALTER TABLE investitionen
        ADD COLUMN IF NOT EXISTS baugruppe_id INTEGER
        REFERENCES baugruppen(id) ON DELETE SET NULL
        """,
    ]
    with engine.begin() as conn:
        for stmt in statements:
            try:
                conn.execute(text(stmt))
            except Exception:
                pass

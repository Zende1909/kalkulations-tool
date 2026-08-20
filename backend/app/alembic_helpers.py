"""Shared Alembic helpers (importable without Alembic runtime context)."""

from __future__ import annotations

from app.config import settings
from app.database import Base

# Register all models on Base.metadata for autogenerate / baseline checks.
from app.models import (  # noqa: F401
    AssemblyPosition,
    Baugruppe,
    BaugruppeKaufteilZuordnung,
    BaugruppeSpritzgussZuordnung,
    BaugruppeVeredelungZuordnung,
    Customer,
    Investition,
    Kaufteil,
    Lohnkosten,
    Maschine,
    Material,
    Program,
    ProgramVolume,
    Project,
    SpritzgussKalkulation,
    SpritzgussVeredelungZuordnung,
    User,
    Veredelungsschritt,
    Zuschlagssatz,
)

target_metadata = Base.metadata


def get_database_url() -> str:
    """Resolve DB URL from application settings (env / .env), never from alembic.ini secrets."""
    return settings.DATABASE_URL

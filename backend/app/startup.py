"""Startup helpers: schema bootstrap vs. read-only Alembic validation."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parent.parent
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
ALEMBIC_SCRIPT_LOCATION = BACKEND_DIR / "alembic"


def get_alembic_script_directory() -> ScriptDirectory:
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
    return ScriptDirectory.from_config(cfg)


def get_alembic_head_revisions() -> tuple[str, ...]:
    heads = tuple(sorted(get_alembic_script_directory().get_heads()))
    if not heads:
        raise RuntimeError("Keine Alembic-Head-Revision gefunden (Script-Directory leer?).")
    return heads


def get_database_alembic_revisions(engine: Engine) -> tuple[str, ...]:
    """Read-only: current revision(s) from alembic_version (empty if unversioned)."""
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return tuple(sorted(context.get_current_heads()))


def warn_if_database_behind_alembic_head(engine: Engine) -> None:
    """Dev-Bootstrap: warnen bei Alembic-Drift, ohne den Start zu blockieren."""
    try:
        expected = set(get_alembic_head_revisions())
        current = set(get_database_alembic_revisions(engine))
    except Exception:
        logger.warning(
            "Alembic-Stand konnte nicht geprüft werden (Dev-Bootstrap).",
            exc_info=True,
        )
        return

    if not current:
        logger.warning(
            "Datenbank ohne alembic_version – bitte `alembic upgrade head` "
            "bzw. kontrolliert `alembic stamp` ausführen. Erwarteter Head: %s",
            ", ".join(sorted(expected)),
        )
        return

    if current != expected:
        logger.warning(
            "Alembic-Migrationsstand hinter dem Code-Head. "
            "Aktuell: %s; erwartet: %s. Bitte `alembic upgrade head` ausführen, "
            "sonst drohen UndefinedColumn-/Schemafehler (z. B. Veredelungs-Snapshots).",
            ", ".join(sorted(current)),
            ", ".join(sorted(expected)),
        )
        return

    logger.info("Alembic-Stand OK (Dev): revision(s)=%s", ", ".join(sorted(current)))


def verify_database_at_alembic_head(engine: Engine) -> None:
    """Fail fast if DB is missing alembic_version or is not at script head(s).

    Read-only: does not stamp, upgrade, or mutate application data.
    """
    expected = set(get_alembic_head_revisions())
    current = set(get_database_alembic_revisions(engine))

    if not current:
        raise RuntimeError(
            "Datenbank ist nicht Alembic-versioniert (Tabelle alembic_version fehlt "
            "oder ist leer). Produktionsstart ohne Schema-Bootstrap erfordert "
            "`alembic upgrade head` (frische DB) bzw. nach ausdrücklicher Freigabe "
            "`alembic stamp <revision>` (bereits vorhandenes Schema)."
        )

    if current != expected:
        raise RuntimeError(
            "Alembic-Migrationsstand weicht vom erwarteten Head ab. "
            f"Aktuell: {sorted(current)}; erwartet: {sorted(expected)}. "
            "Bitte Migrationen kontrolliert auf den Head bringen "
            "(`alembic upgrade head`), bevor die API in Produktion startet."
        )

    logger.info(
        "Alembic-Stand OK: revision(s)=%s",
        ", ".join(sorted(current)),
    )

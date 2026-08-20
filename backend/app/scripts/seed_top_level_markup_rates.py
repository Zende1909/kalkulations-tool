"""Idempotenter Seed für TOP_LEVEL-Zuschlagssätze (vvgk, gewinn, skonto).

Nur explizit per CLI – nie im App-Startup, nie über Alembic.

Aufruf (aus backend/):

    python -m app.scripts.seed_top_level_markup_rates

Voraussetzungen: lokale DATABASE_URL (localhost / 127.0.0.1 / sqlite).
Legt nur fehlende aktive Sätze für vvgk, gewinn und skonto an.
Bestehende GEMEINKOSTEN-, GEWINN- und VERSCHROTTUNG-Datensätze bleiben
unverändert.
"""

from __future__ import annotations

import sys

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.models.zuschlagssatz import ASSEMBLY_MARKUP_TYPEN, Zuschlagssatz

TOP_LEVEL_MARKUP_SEED: tuple[tuple[str, str, float], ...] = (
    ("vvgk", "VVGK", 10.0),
    ("gewinn", "Gewinn", 15.0),
    ("skonto", "Skonto", 0.0),
)


def is_local_development_database(database_url: str) -> bool:
    """Nur lokale Dev-/Test-DBs; keine Sicherheitsgrenze für Netzwerkzugriff."""
    return Settings.is_local_development_database_url(database_url)


def seed_top_level_markup_rates(db: Session) -> list[str]:
    """Legt je technischem Typ höchstens einen aktiven Satz an.

    Returns:
        Liste der durchgeführten Aktionen (insert/skip).
    """
    if set(typ for typ, _, _ in TOP_LEVEL_MARKUP_SEED) != set(ASSEMBLY_MARKUP_TYPEN):
        raise RuntimeError("TOP_LEVEL_MARKUP_SEED stimmt nicht mit ASSEMBLY_MARKUP_TYPEN überein.")

    actions: list[str] = []
    for typ, bezeichnung, satz_prozent in TOP_LEVEL_MARKUP_SEED:
        existing_active = db.scalars(
            select(Zuschlagssatz).where(
                Zuschlagssatz.typ == typ,
                Zuschlagssatz.aktiv.is_(True),
            )
        ).first()
        if existing_active is not None:
            actions.append(f"skip:{typ}")
            continue
        db.add(
            Zuschlagssatz(
                bezeichnung=bezeichnung,
                satz_prozent=satz_prozent,
                typ=typ,
                aktiv=True,
            )
        )
        actions.append(f"insert:{typ}")
    db.commit()
    return actions


def assert_local_development_database(database_url: str) -> None:
    if not is_local_development_database(database_url):
        raise RuntimeError(
            "Seed für TOP_LEVEL-Zuschlagssätze ist nur für lokale "
            "Entwicklungsdatenbanken (localhost/127.0.0.1/sqlite) erlaubt."
        )


def main(argv: list[str] | None = None) -> int:
    """CLI entry: Local-DB-Guard, dann idempotenter Seed."""
    _ = argv  # reserved for future flags
    from app.config import settings

    try:
        assert_local_development_database(settings.DATABASE_URL)
    except RuntimeError as exc:
        print(f"Markup-Seed abgelehnt: {exc}", file=sys.stderr)
        return 1

    from app.database import SessionLocal

    session = SessionLocal()
    try:
        result = seed_top_level_markup_rates(session)
        print("seed_top_level_markup_rates:", ", ".join(result))
        return 0
    except Exception as exc:
        # No secret values in messages/logs.
        print(f"Markup-Seed fehlgeschlagen: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())

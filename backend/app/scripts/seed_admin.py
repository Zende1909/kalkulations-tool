"""Lokaler Admin-Seed – nur explizit per CLI, nie im App-Startup.

Aufruf (aus backend/):

    set LOCAL_ADMIN_SEED_ENABLED=true
    set LOCAL_ADMIN_EMAIL=j.zende@zende-consultant.de
    set LOCAL_ADMIN_PASSWORD=...
    python -m app.scripts.seed_admin

Voraussetzungen: lokale DATABASE_URL (localhost/127.0.0.1/sqlite) und
gesetzte Zugangsdaten. Bestehende Benutzer werden nicht verändert.
"""

from __future__ import annotations

import sys

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import UserRole
from app.crud import user as user_crud
from app.schemas.auth import UserCreate


def seed_admin_user(db: Session) -> str | None:
    """Idempotent: legt optional einen lokalen Admin an.

    Returns:
        \"created\" | \"skipped\" wenn aktiviert und ausgeführt;
        None wenn LOCAL_ADMIN_SEED_ENABLED aus ist (No-Op).
    """
    if not settings.LOCAL_ADMIN_SEED_ENABLED:
        return None

    # Seed must be explicitly local; otherwise "oops" seeds can happen on production DBs.
    if not settings.is_local_development_database_url(settings.DATABASE_URL):
        raise RuntimeError(
            "Local admin seed is enabled, but DATABASE_URL does not look like a local development DB."
        )

    if not settings.LOCAL_ADMIN_EMAIL or not settings.LOCAL_ADMIN_PASSWORD:
        raise RuntimeError(
            "Local admin seed enabled, but LOCAL_ADMIN_EMAIL/LOCAL_ADMIN_PASSWORD are missing."
        )

    existing = user_crud.user.get_by_email(db, email=settings.LOCAL_ADMIN_EMAIL)
    if existing:
        return "skipped"

    try:
        user_crud.user.create(
            db,
            UserCreate(
                email=settings.LOCAL_ADMIN_EMAIL,
                password=settings.LOCAL_ADMIN_PASSWORD,
                role=UserRole.ADMIN,
                is_active=True,
            ),
        )
    except SQLAlchemyError as exc:
        # No secret values in messages/logs.
        raise RuntimeError("Failed to seed local admin user.") from exc
    return "created"


def main(argv: list[str] | None = None) -> int:
    """CLI entry: enforce explicit activation, then run seed_admin_user."""
    _ = argv  # reserved for future flags
    if not settings.LOCAL_ADMIN_SEED_ENABLED:
        print(
            "Admin-Seed abgelehnt: LOCAL_ADMIN_SEED_ENABLED ist nicht aktiv.",
            file=sys.stderr,
        )
        return 1

    from app.database import SessionLocal

    session = SessionLocal()
    try:
        result = seed_admin_user(session)
        print(f"seed_admin_user: {result}")
        return 0
    except RuntimeError as exc:
        print(f"Admin-Seed fehlgeschlagen: {exc}", file=sys.stderr)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())

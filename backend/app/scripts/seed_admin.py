from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.core.security import UserRole
from app.config import settings
from app.crud import user as user_crud
from app.schemas.auth import UserCreate


def seed_admin_user(db: Session) -> None:
    if not settings.LOCAL_ADMIN_SEED_ENABLED:
        return

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
        return

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
        # Let the startup fail in dev if seeding is misconfigured; no secret values in messages/logs.
        raise RuntimeError("Failed to seed local admin user.") from exc

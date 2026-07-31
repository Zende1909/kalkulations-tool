from sqlalchemy.orm import Session

from app.core.security import UserRole
from app.crud import user as user_crud
from app.schemas.auth import UserCreate


def seed_admin_user(db: Session) -> None:
    existing = user_crud.user.get_by_email(db, email="admin@example.com")
    if existing:
        return

    user_crud.user.create(
        db,
        UserCreate(
            email="admin@example.com",
            password="admin123",
            role=UserRole.ADMIN,
            is_active=True,
        ),
    )

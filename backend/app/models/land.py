"""Länder / Regionen für standortabhängige Kosten."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import TimestampMixin

if TYPE_CHECKING:
    from app.models.werk import Werk


class Land(Base, TimestampMixin):
    __tablename__ = "laender"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    werke: Mapped[list[Werk]] = relationship("Werk", back_populates="land")

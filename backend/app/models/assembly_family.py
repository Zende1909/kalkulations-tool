"""Baugruppenfamilie mit variantenspezifischen Anteilen (Mix)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import TimestampMixin

if TYPE_CHECKING:
    from app.models.baugruppe import Baugruppe


class AssemblyFamily(Base, TimestampMixin):
    """Baugruppenfamilie: mehrere Varianten mit Anteilen an der Projektstückzahl."""

    __tablename__ = "assembly_families"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="entwurf")
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Snapshot der Mix-/Mengen-/Kostenaggregation
    ergebnis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    variants: Mapped[list["Baugruppe"]] = relationship(
        "Baugruppe",
        back_populates="assembly_family",
        foreign_keys="Baugruppe.family_id",
    )

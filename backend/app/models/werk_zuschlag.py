"""Werkbezogene Zuschlagssätze (Overrides / Zusatz wie OEM-Handling)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import TimestampMixin

if TYPE_CHECKING:
    from app.models.werk import Werk

WERK_ZUSCHLAG_TYPEN = (
    "fgk",
    "vvgk",
    "gewinn",
    "skonto",
    "mgk_kaufteil_selbst",
    "mgk_kaufteil_oem",
    "handling_oem_kaufteil",
    "overhead_raw_material_excel",
)


class WerkZuschlag(Base, TimestampMixin):
    __tablename__ = "werk_zuschlaege"
    __table_args__ = (
        UniqueConstraint("werk_id", "typ", name="uq_werk_zuschlag_werk_typ"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    werk_id: Mapped[int] = mapped_column(
        ForeignKey("werke.id", ondelete="CASCADE"), nullable=False, index=True
    )
    typ: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    satz_prozent: Mapped[float] = mapped_column(Float, nullable=False)
    kostenbasis: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    werk: Mapped[Werk] = relationship("Werk", back_populates="zuschlaege")

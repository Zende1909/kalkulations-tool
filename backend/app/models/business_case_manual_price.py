"""Manuelle Stückpreise für Business-Case-Szenarien."""

from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin

ASSIGNMENT_TYPES = ("einzelteil", "baugruppe")


class BusinessCaseManualPrice(Base, TimestampMixin):
    __tablename__ = "business_case_manual_prices"
    __table_args__ = (
        UniqueConstraint(
            "customer_id",
            "program_id",
            "linked_project_id",
            "assignment_type",
            "object_id",
            name="uq_bc_manual_price_scope",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    linked_project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    object_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    bottom_price_per_piece: Mapped[float | None] = mapped_column(Float, nullable=True)
    actual_price_per_piece: Mapped[float | None] = mapped_column(Float, nullable=True)

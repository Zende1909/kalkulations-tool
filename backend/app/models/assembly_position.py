"""Positionen in der mehrstufigen Baugruppenstruktur (Phase A – Schema only)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import TimestampMixin

POSITION_TYPES = ("PART", "PURCHASED_PART", "SUBASSEMBLY", "PROCESS")
PRICE_BASES = ("COST", "SELF_COST", "SALES_PRICE")


class AssemblyPosition(Base, TimestampMixin):
    """Einheitliche Positionszeile innerhalb einer Baugruppe."""

    __tablename__ = "assembly_positions"
    __table_args__ = (
        CheckConstraint(
            "position_type IN ('PART', 'PURCHASED_PART', 'SUBASSEMBLY', 'PROCESS')",
            name="chk_ap_position_type",
        ),
        CheckConstraint(
            "price_basis IS NULL OR price_basis IN ('COST', 'SELF_COST', 'SALES_PRICE')",
            name="chk_ap_price_basis",
        ),
        CheckConstraint("sequence >= 1", name="chk_ap_sequence_positive"),
        CheckConstraint("quantity > 0", name="chk_ap_quantity_positive"),
        CheckConstraint("quantity_factor > 0", name="chk_ap_quantity_factor_positive"),
        CheckConstraint(
            """
            position_type <> 'PART'
            OR (
                part_calculation_id IS NOT NULL
                AND purchased_part_id IS NULL
                AND child_assembly_id IS NULL
                AND finishing_step_id IS NULL
                AND price_basis IS NOT NULL
            )
            """,
            name="chk_ap_part_refs",
        ),
        CheckConstraint(
            """
            position_type <> 'PURCHASED_PART'
            OR (
                purchased_part_id IS NOT NULL
                AND part_calculation_id IS NULL
                AND child_assembly_id IS NULL
                AND finishing_step_id IS NULL
                AND price_basis IS NULL
            )
            """,
            name="chk_ap_purchased_refs",
        ),
        CheckConstraint(
            """
            position_type <> 'SUBASSEMBLY'
            OR (
                child_assembly_id IS NOT NULL
                AND part_calculation_id IS NULL
                AND purchased_part_id IS NULL
                AND finishing_step_id IS NULL
                AND price_basis IS NOT NULL
            )
            """,
            name="chk_ap_subassembly_refs",
        ),
        CheckConstraint(
            """
            position_type <> 'PROCESS'
            OR (
                finishing_step_id IS NOT NULL
                AND part_calculation_id IS NULL
                AND purchased_part_id IS NULL
                AND child_assembly_id IS NULL
                AND price_basis IS NULL
            )
            """,
            name="chk_ap_process_refs",
        ),
        Index("uq_ap_parent_sequence", "parent_assembly_id", "sequence", unique=True),
        Index(
            "uq_ap_parent_part",
            "parent_assembly_id",
            "part_calculation_id",
            unique=True,
            postgresql_where=text("position_type = 'PART'"),
            sqlite_where=text("position_type = 'PART'"),
        ),
        Index("idx_ap_parent_assembly", "parent_assembly_id"),
        Index(
            "idx_ap_child_assembly",
            "child_assembly_id",
            postgresql_where=text("child_assembly_id IS NOT NULL"),
            sqlite_where=text("child_assembly_id IS NOT NULL"),
        ),
        Index(
            "idx_ap_part_calculation",
            "part_calculation_id",
            postgresql_where=text("part_calculation_id IS NOT NULL"),
            sqlite_where=text("part_calculation_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    parent_assembly_id: Mapped[int] = mapped_column(
        ForeignKey("baugruppen.id", ondelete="CASCADE"),
        nullable=False,
    )
    position_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    quantity: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    quantity_factor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    price_basis: Mapped[str | None] = mapped_column(String(16), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)

    part_calculation_id: Mapped[int | None] = mapped_column(
        ForeignKey("spritzguss_kalkulationen.id", ondelete="RESTRICT"),
        nullable=True,
    )
    purchased_part_id: Mapped[int | None] = mapped_column(
        ForeignKey("kaufteile.id", ondelete="RESTRICT"),
        nullable=True,
    )
    child_assembly_id: Mapped[int | None] = mapped_column(
        ForeignKey("baugruppen.id", ondelete="RESTRICT"),
        nullable=True,
    )
    finishing_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("veredelungsschritte.id", ondelete="RESTRICT"),
        nullable=True,
    )

    cost_snapshot: Mapped[float | None] = mapped_column(Float, nullable=True)
    price_snapshot: Mapped[float | None] = mapped_column(Float, nullable=True)
    name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    part_number_snapshot: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    supplier_snapshot: Mapped[str] = mapped_column(String(255), nullable=False, default="")

    snapshots_captured_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    parent_assembly: Mapped["Baugruppe"] = relationship(
        "Baugruppe",
        back_populates="assembly_positions",
        foreign_keys=[parent_assembly_id],
    )

from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Investition(Base, TimestampMixin):
    """Investitionen – Werkzeuge, Anlagen, Einmalzahlungen und Amortisationen."""

    __tablename__ = "investitionen"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    investment_type: Mapped[str] = mapped_column(String(64), nullable=False, default="Werkzeug")
    payment_type: Mapped[str] = mapped_column(String(64), nullable=False, default="Einmalzahlung")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    amortization_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_per_piece: Mapped[float | None] = mapped_column(Float, nullable=True)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    customer: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    part_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    part_number: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    calculation_id: Mapped[int | None] = mapped_column(
        ForeignKey("spritzguss_kalkulationen.id"), nullable=True, index=True
    )
    baugruppe_id: Mapped[int | None] = mapped_column(
        ForeignKey("baugruppen.id", ondelete="SET NULL"), nullable=True, index=True
    )
    supplier: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    order_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="In Planung", index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    included_in_unit_price: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

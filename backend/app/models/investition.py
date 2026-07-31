from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Investition(Base, TimestampMixin):
    """Investitionen / Einmalzahlungen (z. B. Werkzeug)."""

    __tablename__ = "investitionen"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    project_id: Mapped[str] = mapped_column(String(255), nullable=False, default="", index=True)
    calculation_id: Mapped[int | None] = mapped_column(
        ForeignKey("spritzguss_kalkulationen.id"), nullable=True, index=True
    )
    part_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    investment_type: Mapped[str] = mapped_column(String(64), nullable=False, default="Werkzeug")
    payment_type: Mapped[str] = mapped_column(String(64), nullable=False, default="Einmalzahlung")
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="offen")

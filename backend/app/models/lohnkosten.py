from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin

LOHN_ROLLEN = ("produktion", "setup", "sonstig")


class Lohnkosten(Base, TimestampMixin):
    __tablename__ = "lohnkosten"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    # EUR/h – Anzeige- und Kalkulationsbasis
    kosten_pro_stunde: Mapped[float] = mapped_column(Float, nullable=False)
    kostenstelle: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    gueltig_ab: Mapped[date] = mapped_column(Date, nullable=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    werk_id: Mapped[int | None] = mapped_column(
        ForeignKey("werke.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rolle: Mapped[str] = mapped_column(String(32), nullable=False, default="sonstig")
    source_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)
    source_rate: Mapped[float | None] = mapped_column(Float, nullable=True)

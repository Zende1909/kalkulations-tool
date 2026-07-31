from datetime import date

from sqlalchemy import Boolean, Date, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Lohnkosten(Base, TimestampMixin):
    __tablename__ = "lohnkosten"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    kosten_pro_stunde: Mapped[float] = mapped_column(Float, nullable=False)
    kostenstelle: Mapped[str] = mapped_column(String(50), nullable=False)
    gueltig_ab: Mapped[date] = mapped_column(Date, nullable=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

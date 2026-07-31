from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Zuschlagssatz(Base, TimestampMixin):
    __tablename__ = "zuschlagssaetze"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    satz_prozent: Mapped[float] = mapped_column(Float, nullable=False)
    typ: Mapped[str] = mapped_column(String(50), nullable=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

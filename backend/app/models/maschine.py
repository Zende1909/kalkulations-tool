from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Maschine(Base, TimestampMixin):
    __tablename__ = "maschinen"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    maschinen_nr: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    stundensatz: Mapped[float] = mapped_column(Float, nullable=False)
    schliesskraft_t: Mapped[float] = mapped_column(Float, nullable=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

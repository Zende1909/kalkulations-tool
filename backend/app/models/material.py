from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Material(Base, TimestampMixin):
    __tablename__ = "materialien"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    material_nr: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    preis_pro_kg: Mapped[float] = mapped_column(Float, nullable=False)
    dichte: Mapped[float] = mapped_column(Float, nullable=False)
    waehrung: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    injection_pressure_kg_cm2: Mapped[float] = mapped_column(Float, nullable=False, default=500.0)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

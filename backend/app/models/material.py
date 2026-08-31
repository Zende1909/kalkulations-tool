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

    # Thermische Daten für die Kühlzeitberechnung (IKET).
    # Die Schmelzdichte ist bewusst getrennt von `dichte` (Feststoff) geführt.
    materialgruppe: Mapped[str | None] = mapped_column(String(32), nullable=True)
    schmelzdichte_kg_m3: Mapped[float | None] = mapped_column(Float, nullable=True)
    waermekapazitaet_j_kg_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    waermeleitfaehigkeit_w_m_k: Mapped[float | None] = mapped_column(Float, nullable=True)
    werkzeugtemperatur_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    schmelzetemperatur_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    entformungstemperatur_c: Mapped[float | None] = mapped_column(Float, nullable=True)

    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Materialgruppe(Base, TimestampMixin):
    """Thermische Kennwerte je Materialgruppe für die Zykluszeit-Schätzung."""

    __tablename__ = "materialgruppen"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    gruppe: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    schmelzdichte_kg_m3: Mapped[float] = mapped_column(Float, nullable=False)
    waermekapazitaet_j_kg_k: Mapped[float] = mapped_column(Float, nullable=False)
    waermeleitfaehigkeit_w_m_k: Mapped[float] = mapped_column(Float, nullable=False)
    werkzeugtemperatur_c: Mapped[float] = mapped_column(Float, nullable=False)
    schmelzetemperatur_c: Mapped[float] = mapped_column(Float, nullable=False)
    entformungstemperatur_c: Mapped[float] = mapped_column(Float, nullable=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

"""Werke / Produktionsstandorte."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import TimestampMixin

if TYPE_CHECKING:
    from app.models.land import Land
    from app.models.werk_zuschlag import WerkZuschlag


class Werk(Base, TimestampMixin):
    """Produktionsstandort inkl. standortbezogener Costing-Parameter.

    Standort-/Betriebsparameter (Kapazität, Sätze, Energiepreise) leben am Werk.
    Maschinenabhängige Größen (Investment, Fläche, Verbräuche, Setup-Zeit)
    bleiben an der Maschine; der Stundensatz kombiniert beide.
    """

    __tablename__ = "werke"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    land_id: Mapped[int] = mapped_column(
        ForeignKey("laender.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    fx_to_eur: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Kapazitätsmodell (Mappe1 Globals)
    arbeitstage_pro_jahr: Mapped[float | None] = mapped_column(Float, nullable=True)
    schichten_pro_tag: Mapped[float | None] = mapped_column(Float, nullable=True)
    stunden_pro_schicht: Mapped[float | None] = mapped_column(Float, nullable=True)
    oee: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Standort-Kostensätze (Quellwährung)
    space_cost_satz_pro_sqm_jahr: Mapped[float | None] = mapped_column(Float, nullable=True)
    abschreibungsdauer_jahre: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Standort-/Kapitalkostensätze: intern Anteile 0–1 (UI zeigt % und wandelt /100).
    # OEE bleibt Anteil (0–1), keine Prozentpunkt-Umwandlung.
    zinssatz: Mapped[float | None] = mapped_column(Float, nullable=True)
    versicherungssatz: Mapped[float | None] = mapped_column(Float, nullable=True)
    instandhaltungssatz: Mapped[float | None] = mapped_column(Float, nullable=True)
    strompreis: Mapped[float | None] = mapped_column(Float, nullable=True)
    druckluftpreis: Mapped[float | None] = mapped_column(Float, nullable=True)
    kuehlwasserpreis: Mapped[float | None] = mapped_column(Float, nullable=True)

    land: Mapped[Land] = relationship("Land", back_populates="werke")
    zuschlaege: Mapped[list[WerkZuschlag]] = relationship(
        "WerkZuschlag", back_populates="werk", cascade="all, delete-orphan"
    )

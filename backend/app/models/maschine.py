"""Maschine – optional werkbezogen mit Costing-Base-Parametern."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Maschine(Base, TimestampMixin):
    __tablename__ = "maschinen"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    maschinen_nr: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    # EUR/h – Abwärtskompatibilität; bei Parameter-Neuberechnung aktualisiert
    stundensatz: Mapped[float] = mapped_column(Float, nullable=False)
    schliesskraft_t: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    werk_id: Mapped[int | None] = mapped_column(
        ForeignKey("werke.id", ondelete="SET NULL"), nullable=True, index=True
    )
    maschinentyp: Mapped[str | None] = mapped_column(String(128), nullable=True)
    variante: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_currency: Mapped[str | None] = mapped_column(String(8), nullable=True)

    # Kapazitätsmodell
    arbeitstage_pro_jahr: Mapped[float | None] = mapped_column(Float, nullable=True)
    schichten_pro_tag: Mapped[float | None] = mapped_column(Float, nullable=True)
    stunden_pro_schicht: Mapped[float | None] = mapped_column(Float, nullable=True)
    oee: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Investment & Space (Quellwährung)
    investment: Mapped[float | None] = mapped_column(Float, nullable=True)
    flaeche_sqm: Mapped[float | None] = mapped_column(Float, nullable=True)
    space_cost_satz_pro_sqm_jahr: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Kapitalkosten-Sätze
    abschreibungsdauer_jahre: Mapped[float | None] = mapped_column(Float, nullable=True)
    zinssatz: Mapped[float | None] = mapped_column(Float, nullable=True)
    versicherungssatz: Mapped[float | None] = mapped_column(Float, nullable=True)
    instandhaltungssatz: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Energie / Versorgung (Verbrauch je Stunde × Preis)
    stromverbrauch_kwh_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    strompreis: Mapped[float | None] = mapped_column(Float, nullable=True)
    druckluftverbrauch_m3_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    druckluftpreis: Mapped[float | None] = mapped_column(Float, nullable=True)
    kuehlwasserverbrauch_m3_h: Mapped[float | None] = mapped_column(Float, nullable=True)
    kuehlwasserpreis: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Setup
    setup_zeit_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    setup_mitarbeiter: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Berechnete Werte (Cache, Quellwährung bzw. EUR)
    jahresstunden: Mapped[float | None] = mapped_column(Float, nullable=True)
    space_costs_pro_stunde: Mapped[float | None] = mapped_column(Float, nullable=True)
    abschreibung_pro_stunde: Mapped[float | None] = mapped_column(Float, nullable=True)
    zinsen_pro_stunde: Mapped[float | None] = mapped_column(Float, nullable=True)
    versicherung_pro_stunde: Mapped[float | None] = mapped_column(Float, nullable=True)
    instandhaltung_pro_stunde: Mapped[float | None] = mapped_column(Float, nullable=True)
    energie_pro_stunde: Mapped[float | None] = mapped_column(Float, nullable=True)
    stundensatz_source: Mapped[float | None] = mapped_column(Float, nullable=True)
    rate_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

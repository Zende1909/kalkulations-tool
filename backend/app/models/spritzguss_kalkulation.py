from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class SpritzgussKalkulation(Base, TimestampMixin):
    __tablename__ = "spritzguss_kalkulationen"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # Allgemein
    teilebezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    teilenummer: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    kunde: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    projekt: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    jahresstueckzahl: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Material
    material_id: Mapped[int | None] = mapped_column(ForeignKey("materialien.id"), nullable=True)
    schussgewicht_g: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    teilegewicht_netto_g: Mapped[float] = mapped_column(Float, nullable=False)
    ausschussquote_pct: Mapped[float] = mapped_column(Float, nullable=False)
    materialpreis_pro_kg: Mapped[float] = mapped_column(Float, nullable=False)

    # Maschine
    maschine_id: Mapped[int | None] = mapped_column(ForeignKey("maschinen.id"), nullable=True)
    zykluszeit_s: Mapped[float] = mapped_column(Float, nullable=False)
    kavitaeten: Mapped[int] = mapped_column(Integer, nullable=False)
    maschinenstundensatz: Mapped[float] = mapped_column(Float, nullable=False)

    # Lohn
    lohnkosten_id: Mapped[int | None] = mapped_column(ForeignKey("lohnkosten.id"), nullable=True)
    lohnstundensatz: Mapped[float] = mapped_column(Float, nullable=False)

    # Werkzeug
    werkzeugkosten_eur: Mapped[float] = mapped_column(Float, nullable=False)
    amortisationsvolumen: Mapped[float] = mapped_column(Float, nullable=False)

    # Zuschläge
    mgk_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fgk_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    vvgk_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    gewinn_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    skonto_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    # Zuletzt berechnetes Ergebnis (JSON)
    ergebnis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ergebnis_bloecke: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    notizen: Mapped[str] = mapped_column(Text, nullable=False, default="")
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

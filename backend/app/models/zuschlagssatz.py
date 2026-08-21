from sqlalchemy import Boolean, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin

STAMMDATEN_ZUSCHLAGSSATZ_TYPEN = ("GEMEINKOSTEN", "GEWINN", "VERSCHROTTUNG")
# TOP_LEVEL / zentrale automatische Zuschläge (lowercase keys).
CENTRAL_MARKUP_TYPEN = (
    "mgk_kaufteil_selbst",
    "mgk_kaufteil_oem",
    "fgk",
    "vvgk",
    "gewinn",
    "skonto",
)
# Abwärtskompatibler Alias: bisherige Assembly-Markups ⊆ CENTRAL_MARKUP_TYPEN
ASSEMBLY_MARKUP_TYPEN = ("vvgk", "gewinn", "skonto")
ALLOWED_ZUSCHLAGSSATZ_TYPEN = STAMMDATEN_ZUSCHLAGSSATZ_TYPEN + CENTRAL_MARKUP_TYPEN


class Zuschlagssatz(Base, TimestampMixin):
    __tablename__ = "zuschlagssaetze"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    satz_prozent: Mapped[float] = mapped_column(Float, nullable=False)
    typ: Mapped[str] = mapped_column(String(50), nullable=False)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

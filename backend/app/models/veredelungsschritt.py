from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Veredelungsschritt(Base, TimestampMixin):
    __tablename__ = "veredelungsschritte"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    veredelungsart: Mapped[str] = mapped_column(String(64), nullable=False)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=1, index=True)
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False, default="")

    taktzeit_s: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    anzahl_mitarbeiter: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    lohnkosten_id: Mapped[int | None] = mapped_column(
        ForeignKey("lohnkosten.id"), nullable=True
    )
    lohnstundensatz: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    maschinenstundensatz: Mapped[float | None] = mapped_column(Float, nullable=True)

    verbrauchskosten_je_stueck: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    ausschussquote_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    fgk_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0)

    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

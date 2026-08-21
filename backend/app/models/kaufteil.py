from datetime import date

from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Kaufteil(Base, TimestampMixin):
    """Zentral gepflegte Kaufteile für Baugruppenkalkulationen."""

    __tablename__ = "kaufteile"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    artikelnummer: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False)
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False, default="")
    lieferant: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    einheit: Mapped[str] = mapped_column(String(32), nullable=False, default="Stück")
    preis: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    waehrung: Mapped[str] = mapped_column(String(8), nullable=False, default="EUR")
    gueltig_ab: Mapped[date | None] = mapped_column(Date, nullable=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # selbstnominiert | oem_nominiert | None (Altbestand ohne Klassifizierung)
    nominierung: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    customer_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    program_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("programs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )

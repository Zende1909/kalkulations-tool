from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class Baugruppe(Base, TimestampMixin):
    """Baugruppenkalkulation – Zusammenführung von Einzelteilen, Kaufteilen und Veredelung."""

    __tablename__ = "baugruppen"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    teilenummer: Mapped[str] = mapped_column(String(100), nullable=False, default="", index=True)
    kunde: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    projekt: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    jahresstueckzahl: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    beschreibung: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="entwurf")
    ergebnis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ergebnis_bloecke: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    linked_project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )


class BaugruppeSpritzgussZuordnung(Base, TimestampMixin):
    """Einzelteil-Zuordnung in einer Baugruppe inkl. Preis-Snapshot."""

    __tablename__ = "baugruppe_spritzguss_zuordnungen"
    __table_args__ = (
        UniqueConstraint(
            "baugruppe_id",
            "spritzguss_kalkulation_id",
            name="uq_baugruppe_spritzguss",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    baugruppe_id: Mapped[int] = mapped_column(
        ForeignKey("baugruppen.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    spritzguss_kalkulation_id: Mapped[int] = mapped_column(
        ForeignKey("spritzguss_kalkulationen.id"),
        nullable=False,
        index=True,
    )
    menge: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot_preis: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    snapshot_bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    snapshot_teilenummer: Mapped[str] = mapped_column(String(100), nullable=False, default="")


class BaugruppeKaufteilZuordnung(Base, TimestampMixin):
    """Kaufteil-Zuordnung in einer Baugruppe inkl. überschreibbarem Preis-Snapshot."""

    __tablename__ = "baugruppe_kaufteil_zuordnungen"
    __table_args__ = (
        UniqueConstraint(
            "baugruppe_id",
            "kaufteil_id",
            name="uq_baugruppe_kaufteil",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    baugruppe_id: Mapped[int] = mapped_column(
        ForeignKey("baugruppen.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kaufteil_id: Mapped[int] = mapped_column(
        ForeignKey("kaufteile.id"),
        nullable=False,
        index=True,
    )
    menge: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot_preis: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    snapshot_bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    snapshot_lieferant: Mapped[str] = mapped_column(String(255), nullable=False, default="")


class BaugruppeVeredelungZuordnung(Base, TimestampMixin):
    """Montage-/Veredelungsschritt-Zuordnung in einer Baugruppe inkl. Kosten-Snapshot."""

    __tablename__ = "baugruppe_veredelung_zuordnungen"
    __table_args__ = (
        UniqueConstraint(
            "baugruppe_id",
            "veredelungsschritt_id",
            name="uq_baugruppe_veredelung",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    baugruppe_id: Mapped[int] = mapped_column(
        ForeignKey("baugruppen.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    veredelungsschritt_id: Mapped[int] = mapped_column(
        ForeignKey("veredelungsschritte.id"),
        nullable=False,
        index=True,
    )
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    mengenfaktor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    snapshot_kosten: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    snapshot_bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False, default="")

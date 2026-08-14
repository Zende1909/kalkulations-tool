from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base
from app.models.user import TimestampMixin


class SpritzgussVeredelungZuordnung(Base, TimestampMixin):
    """Verknüpfung Spritzguss-Kalkulation ↔ Veredelungsschritt inkl. Kosten-Snapshot."""

    __tablename__ = "spritzguss_veredelung_zuordnungen"
    __table_args__ = (
        UniqueConstraint(
            "kalkulation_id",
            "veredelungsschritt_id",
            name="uq_spritzguss_veredelung_kalk_schritt",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    kalkulation_id: Mapped[int] = mapped_column(
        ForeignKey("spritzguss_kalkulationen.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    veredelungsschritt_id: Mapped[int] = mapped_column(
        ForeignKey("veredelungsschritte.id"),
        nullable=False,
        index=True,
    )

    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    aktiv: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mengenfaktor: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # Snapshot beim Speichern – historische Kalkulationen bleiben stabil
    snapshot_bezeichnung: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    snapshot_veredelungsart: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    snapshot_kosten_inkl_ausschuss: Mapped[float] = mapped_column(Float, nullable=False, default=0)

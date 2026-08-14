from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import TimestampMixin


PROGRAM_STATUSES = (
    "Anfrage",
    "Angebot",
    "Beauftragt",
    "Laufend",
    "Abgeschlossen",
    "Inaktiv",
)


class Program(Base, TimestampMixin):
    __tablename__ = "programs"
    __table_args__ = (
        UniqueConstraint("customer_id", "program_number", name="uq_program_customer_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    program_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    vehicle_series: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    sop: Mapped[date | None] = mapped_column(Date, nullable=True)
    eop: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Anfrage", index=True)
    production_plant: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    customer: Mapped["Customer"] = relationship(back_populates="programs")
    volumes: Mapped[list["ProgramVolume"]] = relationship(
        back_populates="program",
        cascade="all, delete-orphan",
    )
    projects: Mapped[list["Project"]] = relationship(back_populates="program")


class ProgramVolume(Base, TimestampMixin):
    __tablename__ = "program_volumes"
    __table_args__ = (
        UniqueConstraint("program_id", "calendar_year", name="uq_program_volume_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    calendar_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    vehicle_volume: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    program: Mapped["Program"] = relationship(back_populates="volumes")

from sqlalchemy import Boolean, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.user import TimestampMixin


PROJECT_STATUSES = (
    "Anfrage",
    "Kalkulation",
    "Angebot",
    "Beauftragt",
    "Laufend",
    "Abgeschlossen",
    "Inaktiv",
)


class Project(Base, TimestampMixin):
    __tablename__ = "projects"
    __table_args__ = (
        UniqueConstraint("program_id", "project_number", name="uq_project_program_number"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    project_number: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    component_area: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    quantity_per_vehicle: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="Anfrage", index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    program: Mapped["Program"] = relationship(back_populates="projects")

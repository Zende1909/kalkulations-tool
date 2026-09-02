"""Hilfsfunktionen zum Seeden von Materialgruppen in SQLite-Tests."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.material import Material
from app.models.materialgruppe import Materialgruppe
from app.services.material_thermik import MATERIALGRUPPEN_DEFAULTS


def create_material_tables(engine: Engine) -> None:
    Base.metadata.create_all(engine, tables=[Materialgruppe.__table__, Material.__table__])


def seed_materialgruppen(session: Session) -> None:
    if session.scalar(select(Materialgruppe.id).limit(1)) is not None:
        return
    for d in MATERIALGRUPPEN_DEFAULTS.values():
        session.add(
            Materialgruppe(
                gruppe=d.gruppe,
                bezeichnung=d.bezeichnung,
                schmelzdichte_kg_m3=d.schmelzdichte_kg_m3,
                waermekapazitaet_j_kg_k=d.waermekapazitaet_j_kg_k,
                waermeleitfaehigkeit_w_m_k=d.waermeleitfaehigkeit_w_m_k,
                werkzeugtemperatur_c=d.werkzeugtemperatur_c,
                schmelzetemperatur_c=d.schmelzetemperatur_c,
                entformungstemperatur_c=d.entformungstemperatur_c,
                aktiv=True,
            )
        )
    session.commit()


def material_test_session(engine: Engine) -> Session:
    create_material_tables(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    seed_materialgruppen(session)
    return session

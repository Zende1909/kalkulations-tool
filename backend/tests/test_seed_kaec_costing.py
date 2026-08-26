"""Seed KAEC Costing aus Mappe1 – Idempotenz und IMM-150-Rate."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models.land import Land
from app.models.lohnkosten import Lohnkosten
from app.models.maschine import Maschine
from app.models.werk import Werk
from app.models.werk_zuschlag import WerkZuschlag
from app.scripts.seed_kaec_costing_from_mappe1 import seed_kaec_from_mappe1


REFERENCE = (
    Path(__file__).resolve().parents[1] / "data" / "reference" / "Mappe1.xlsx"
)


@pytest.fixture()
def seed_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Land.__table__,
            Werk.__table__,
            Maschine.__table__,
            Lohnkosten.__table__,
            WerkZuschlag.__table__,
        ],
    )
    SessionLocal = sessionmaker(bind=engine)
    with SessionLocal() as db:
        yield db


@pytest.mark.skipif(not REFERENCE.is_file(), reason="Mappe1.xlsx reference missing")
def test_seed_kaec_idempotent_and_imm150_rate(seed_db: Session):
    actions1 = seed_kaec_from_mappe1(seed_db, xlsx_path=REFERENCE)
    inserts = [a for a in actions1 if a.startswith("insert:maschine:")]
    assert any(a.startswith("insert:werk:") for a in actions1)
    assert len(inserts) >= 1
    assert any("conflict:material_mgk" in a for a in actions1)

    imm = seed_db.scalars(
        select(Maschine).where(Maschine.maschinen_nr.like("KAEC-IMM%150%"))
    ).first()
    # Exact nr depends on Excel typ/variant formatting
    if imm is None:
        imm = seed_db.scalars(
            select(Maschine).where(Maschine.maschinen_nr.contains("150"))
        ).first()
    assert imm is not None
    assert imm.jahresstunden == pytest.approx(3657.6)
    assert imm.stundensatz_source == pytest.approx(17.511, abs=0.05)
    assert imm.stundensatz == pytest.approx(17.511 * 0.92, abs=0.05)

    inactive = seed_db.scalars(
        select(WerkZuschlag).where(WerkZuschlag.typ == "overhead_raw_material_excel")
    ).first()
    assert inactive is not None
    assert inactive.aktiv is False
    assert inactive.satz_prozent == pytest.approx(2.0)

    handling = seed_db.scalars(
        select(WerkZuschlag).where(WerkZuschlag.typ == "handling_oem_kaufteil")
    ).first()
    assert handling is not None
    assert handling.aktiv is True
    assert handling.satz_prozent == pytest.approx(6.0)

    n_before = len(list(seed_db.scalars(select(Maschine)).all()))
    actions2 = seed_kaec_from_mappe1(seed_db, xlsx_path=REFERENCE)
    assert all(not a.startswith("insert:maschine:") for a in actions2)
    assert any(a.startswith("skip:maschine:") for a in actions2)
    n_after = len(list(seed_db.scalars(select(Maschine)).all()))
    assert n_after == n_before

"""Phase-A-Tests: assembly_positions-Modell und additive Migration."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.db_upgrade import ensure_assembly_structure_schema
from app.models.assembly_position import POSITION_TYPES, PRICE_BASES, AssemblyPosition
from app.models.baugruppe import ASSEMBLY_TYPES, PRICING_STATUSES, Baugruppe


def _create_sqlite_phase_a_schema(engine) -> None:
    """Minimales Schema für SQLite-Tests (ohne JSONB)."""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS baugruppen (
            id INTEGER PRIMARY KEY,
            name VARCHAR(255) NOT NULL DEFAULT '',
            teilenummer VARCHAR(100) NOT NULL DEFAULT '',
            kunde VARCHAR(255) NOT NULL DEFAULT '',
            projekt VARCHAR(255) NOT NULL DEFAULT '',
            jahresstueckzahl INTEGER NOT NULL DEFAULT 0,
            beschreibung TEXT NOT NULL DEFAULT '',
            status VARCHAR(32) NOT NULL DEFAULT 'entwurf',
            aktiv BOOLEAN NOT NULL DEFAULT 1,
            linked_project_id INTEGER,
            project_id INTEGER REFERENCES projects(id),
            werk_id INTEGER,
            assembly_type VARCHAR(16) NOT NULL DEFAULT 'TOP_LEVEL',
            structure_version INTEGER NOT NULL DEFAULT 1,
            legacy_mode BOOLEAN NOT NULL DEFAULT 1,
            pricing_status VARCHAR(32) NOT NULL DEFAULT 'NOT_APPLICABLE',
            ergebnis TEXT,
            ergebnis_bloecke TEXT,
            snapshots_captured_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS spritzguss_kalkulationen (
            id INTEGER PRIMARY KEY,
            teilebezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            teilenummer VARCHAR(100) NOT NULL DEFAULT '',
            teilegewicht_netto_g FLOAT NOT NULL DEFAULT 1,
            ausschussquote_pct FLOAT NOT NULL DEFAULT 0,
            materialpreis_pro_kg FLOAT NOT NULL DEFAULT 0,
            zykluszeit_s FLOAT NOT NULL DEFAULT 1,
            kavitaeten INTEGER NOT NULL DEFAULT 1,
            maschinenstundensatz FLOAT NOT NULL DEFAULT 0,
            lohnstundensatz FLOAT NOT NULL DEFAULT 0,
            werkzeugkosten_eur FLOAT NOT NULL DEFAULT 0,
            werk_id INTEGER,
            losgroesse INTEGER, losgroesse_modus VARCHAR(16), losgroesse_manuell INTEGER
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS kaufteile (
            id INTEGER PRIMARY KEY,
            artikelnummer VARCHAR(100) NOT NULL DEFAULT '',
            bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            preis FLOAT NOT NULL DEFAULT 0,
            waehrung VARCHAR(8) NOT NULL DEFAULT 'EUR',
            einheit VARCHAR(32) NOT NULL DEFAULT 'Stück',
            aktiv BOOLEAN NOT NULL DEFAULT 1
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS veredelungsschritte (
            id INTEGER PRIMARY KEY,
            bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
            veredelungsart VARCHAR(64) NOT NULL DEFAULT '',
            reihenfolge INTEGER NOT NULL DEFAULT 1,
            taktzeit_s FLOAT NOT NULL DEFAULT 0,
            anzahl_mitarbeiter INTEGER NOT NULL DEFAULT 1,
            lohnstundensatz FLOAT NOT NULL DEFAULT 0,
            verbrauchskosten_je_stueck FLOAT NOT NULL DEFAULT 0,
            ausschussquote_pct FLOAT NOT NULL DEFAULT 0,
            fgk_pct FLOAT NOT NULL DEFAULT 0,
            aktiv BOOLEAN NOT NULL DEFAULT 1
        )
        """,
    ]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
    AssemblyPosition.__table__.create(engine, checkfirst=True)


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    _create_sqlite_phase_a_schema(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


def test_enum_constants():
    assert POSITION_TYPES == ("PART", "PURCHASED_PART", "SUBASSEMBLY", "PROCESS")
    assert PRICE_BASES == ("COST", "SELF_COST", "SALES_PRICE")
    assert ASSEMBLY_TYPES == ("TOP_LEVEL", "SUBASSEMBLY")
    assert PRICING_STATUSES == ("NOT_APPLICABLE", "CALCULATED", "STALE")


def test_baugruppe_model_has_phase_a_columns():
    columns = {c.name for c in Baugruppe.__table__.columns}
    assert {
        "project_id",
        "assembly_type",
        "structure_version",
        "legacy_mode",
        "snapshots_captured_at",
        "pricing_status",
        "linked_project_id",
    }.issubset(columns)


def test_assembly_position_model_has_check_constraints():
    names = {c.name for c in AssemblyPosition.__table__.constraints if hasattr(c, "name") and c.name}
    assert "chk_ap_position_type" in names
    assert "chk_ap_part_refs" in names
    assert "chk_ap_process_refs" in names


def test_baugruppe_defaults(db):
    bg = Baugruppe(name="Test-BG")
    db.add(bg)
    db.commit()
    db.refresh(bg)
    assert bg.assembly_type == "TOP_LEVEL"
    assert bg.legacy_mode is True
    assert bg.structure_version == 1
    assert bg.pricing_status == "NOT_APPLICABLE"
    assert bg.project_id is None


def test_insert_process_position(db):
    db.execute(text("INSERT INTO baugruppen (id, name) VALUES (1, 'TOP')"))
    db.execute(text("INSERT INTO veredelungsschritte (id, bezeichnung, veredelungsart) VALUES (10, 'Endmontage', 'MONTAGE')"))
    db.commit()

    pos = AssemblyPosition(
        parent_assembly_id=1,
        position_type="PROCESS",
        sequence=10,
        finishing_step_id=10,
        cost_snapshot=3.0,
        name_snapshot="Endmontage",
    )
    db.add(pos)
    db.commit()
    assert pos.id is not None
    assert pos.price_basis is None


def test_insert_part_position(db):
    db.execute(text("INSERT INTO baugruppen (id, name) VALUES (1, 'SUB')"))
    db.execute(
        text(
            "INSERT INTO spritzguss_kalkulationen (id, teilebezeichnung, teilenummer) "
            "VALUES (501, 'Grundträger', 'GT-001')"
        )
    )
    db.commit()

    pos = AssemblyPosition(
        parent_assembly_id=1,
        position_type="PART",
        sequence=10,
        part_calculation_id=501,
        price_basis="COST",
        cost_snapshot=4.20,
        name_snapshot="Grundträger",
    )
    db.add(pos)
    db.commit()
    assert pos.part_calculation_id == 501


def test_part_position_requires_price_basis(db):
    db.execute(text("INSERT INTO baugruppen (id, name) VALUES (1, 'SUB')"))
    db.execute(
        text(
            "INSERT INTO spritzguss_kalkulationen (id, teilebezeichnung, teilenummer) "
            "VALUES (501, 'Teil', 'T-1')"
        )
    )
    db.commit()

    pos = AssemblyPosition(
        parent_assembly_id=1,
        position_type="PART",
        sequence=10,
        part_calculation_id=501,
        price_basis=None,
    )
    db.add(pos)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_process_position_rejects_price_basis(db):
    db.execute(text("INSERT INTO baugruppen (id, name) VALUES (1, 'TOP')"))
    db.execute(text("INSERT INTO veredelungsschritte (id, bezeichnung, veredelungsart) VALUES (10, 'Schweißen', 'SCHWEISSEN')"))
    db.commit()

    pos = AssemblyPosition(
        parent_assembly_id=1,
        position_type="PROCESS",
        sequence=10,
        finishing_step_id=10,
        price_basis="COST",
    )
    db.add(pos)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_duplicate_sequence_rejected(db):
    db.execute(text("INSERT INTO baugruppen (id, name) VALUES (1, 'TOP')"))
    db.execute(text("INSERT INTO veredelungsschritte (id, bezeichnung, veredelungsart) VALUES (10, 'A', 'MONTAGE')"))
    db.execute(text("INSERT INTO veredelungsschritte (id, bezeichnung, veredelungsart) VALUES (11, 'B', 'MONTAGE')"))
    db.commit()

    db.add(
        AssemblyPosition(
            parent_assembly_id=1,
            position_type="PROCESS",
            sequence=10,
            finishing_step_id=10,
        )
    )
    db.commit()
    db.add(
        AssemblyPosition(
            parent_assembly_id=1,
            position_type="PROCESS",
            sequence=10,
            finishing_step_id=11,
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_multiple_same_child_assembly_allowed(db):
    db.execute(text("INSERT INTO baugruppen (id, name) VALUES (1, 'TOP')"))
    db.execute(text("INSERT INTO baugruppen (id, name, assembly_type) VALUES (2, 'SUB', 'SUBASSEMBLY')"))
    db.commit()

    db.add(
        AssemblyPosition(
            parent_assembly_id=1,
            position_type="SUBASSEMBLY",
            sequence=10,
            child_assembly_id=2,
            price_basis="COST",
            cost_snapshot=16.5,
            name_snapshot="Armauflage links",
            label="Armauflage links",
        )
    )
    db.add(
        AssemblyPosition(
            parent_assembly_id=1,
            position_type="SUBASSEMBLY",
            sequence=20,
            child_assembly_id=2,
            price_basis="COST",
            cost_snapshot=16.5,
            name_snapshot="Armauflage rechts",
            label="Armauflage rechts",
        )
    )
    db.commit()
    rows = db.query(AssemblyPosition).filter(AssemblyPosition.child_assembly_id == 2).all()
    assert len(rows) == 2


def test_same_process_stammdaten_id_allowed_twice(db):
    """Kein Unique auf finishing_step_id – gleicher Stammdaten-Prozess darf mehrfach vorkommen."""
    db.execute(text("INSERT INTO baugruppen (id, name) VALUES (1, 'TOP')"))
    db.execute(text("INSERT INTO veredelungsschritte (id, bezeichnung, veredelungsart) VALUES (33, 'Schweißen', 'SCHWEISSEN')"))
    db.commit()

    db.add(
        AssemblyPosition(
            parent_assembly_id=1,
            position_type="PROCESS",
            sequence=10,
            finishing_step_id=33,
            name_snapshot="Schweißen 1",
        )
    )
    db.add(
        AssemblyPosition(
            parent_assembly_id=1,
            position_type="PROCESS",
            sequence=20,
            finishing_step_id=33,
            name_snapshot="Schweißen 2",
        )
    )
    db.commit()
    assert db.query(AssemblyPosition).filter(AssemblyPosition.finishing_step_id == 33).count() == 2


def test_quantity_must_be_positive(db):
    db.execute(text("INSERT INTO baugruppen (id, name) VALUES (1, 'TOP')"))
    db.execute(text("INSERT INTO kaufteile (id, artikelnummer, bezeichnung) VALUES (1, 'K-1', 'Clip')"))
    db.commit()

    pos = AssemblyPosition(
        parent_assembly_id=1,
        position_type="PURCHASED_PART",
        sequence=10,
        purchased_part_id=1,
        quantity=0,
        price_snapshot=0.2,
    )
    db.add(pos)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_ensure_assembly_structure_schema_idempotent_sqlite():
    engine = create_engine("sqlite:///:memory:")
    _create_sqlite_phase_a_schema(engine)
    ensure_assembly_structure_schema(engine)
    ensure_assembly_structure_schema(engine)
    inspector = inspect(engine)
    assert "assembly_positions" in inspector.get_table_names()


def test_migration_does_not_contain_destructive_sql():
    import inspect as pyinspect

    source = pyinspect.getsource(ensure_assembly_structure_schema)
    upper = source.upper()
    assert "DROP TABLE" not in upper
    assert "DROP COLUMN" not in upper
    assert "TRUNCATE" not in upper
    assert "DELETE FROM" not in upper
    assert "UPDATE BAUGRUPPEN" not in upper

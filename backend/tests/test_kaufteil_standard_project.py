"""Standardkaufteile (project_id IS NULL) und Projektfilter."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.baugruppen import _validate_zuordnungen_project_scope
from app.api.v1.kaufteile import list_kaufteile
from app.models.kaufteil import Kaufteil
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.schemas.baugruppe import KaufteilCreate, KaufteilZuordnungInput, SpritzgussZuordnungInput


def _create_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.execute(
            text(
                """
                CREATE TABLE customers (
                    id INTEGER PRIMARY KEY,
                    customer_number VARCHAR(50) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE programs (
                    id INTEGER PRIMARY KEY,
                    customer_id INTEGER NOT NULL,
                    program_number VARCHAR(50) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    vehicle_series VARCHAR(255) NOT NULL DEFAULT '',
                    status VARCHAR(32) NOT NULL DEFAULT 'Anfrage',
                    production_plant VARCHAR(255) NOT NULL DEFAULT '',
                    notes TEXT NOT NULL DEFAULT '',
                    active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE projects (
                    id INTEGER PRIMARY KEY,
                    program_id INTEGER NOT NULL,
                    project_number VARCHAR(50) NOT NULL,
                    name VARCHAR(255) NOT NULL,
                    component_area VARCHAR(255) NOT NULL DEFAULT '',
                    quantity_per_vehicle FLOAT NOT NULL DEFAULT 1,
                    status VARCHAR(32) NOT NULL DEFAULT 'Anfrage',
                    notes TEXT NOT NULL DEFAULT '',
                    active BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE kaufteile (
                    id INTEGER PRIMARY KEY,
                    artikelnummer VARCHAR(100) NOT NULL,
                    bezeichnung VARCHAR(255) NOT NULL,
                    beschreibung TEXT NOT NULL DEFAULT '',
                    lieferant VARCHAR(255) NOT NULL DEFAULT '',
                    einheit VARCHAR(32) NOT NULL DEFAULT 'Stück',
                    preis FLOAT NOT NULL DEFAULT 0,
                    waehrung VARCHAR(8) NOT NULL DEFAULT 'EUR',
                    gueltig_ab DATE,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    nominierung VARCHAR(32),
                    customer_id INTEGER,
                    program_id INTEGER,
                    project_id INTEGER,
                    sga_override_aktiv BOOLEAN NOT NULL DEFAULT 0,
                    sga_satz_manuell FLOAT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE spritzguss_kalkulationen (
                    id INTEGER PRIMARY KEY,
                    teilebezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                    teilenummer VARCHAR(100) NOT NULL DEFAULT '',
                    project_id INTEGER,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    maschinen_groesse_modus VARCHAR(16),
                    maschinen_groesse_breite_mm FLOAT,
                    maschinen_groesse_laenge_mm FLOAT,
                    maschinen_groesse_oeffnungen_pct FLOAT,
                    maschinen_groesse_proj_flaeche_mm2 FLOAT,
                    maschinen_groesse_schwindung_pct FLOAT,
                    maschinen_groesse_injection_pressure_kg_cm2 FLOAT,
                    maschinen_groesse_proj_flaeche_netto_mm2 FLOAT,
                    maschinen_groesse_zuhaltekraft_ohne_sicherheit_t FLOAT,
                    maschinen_groesse_sicherheitszuschlag_faktor FLOAT,
                    maschinen_groesse_zuhaltekraft_erforderlich_t FLOAT,
                    maschinen_groesse_empfohlene_maschine_id INTEGER,
                    maschinen_groesse_warnung VARCHAR(512),
                    zykluszeit_quelle VARCHAR(16),
                    zykluszeit_wandstaerke_mm FLOAT,
                    zykluszeit_variante INTEGER,
                    zykluszeit_kuehlfaktor FLOAT,
                    zykluszeit_komponenten INTEGER,
                    zykluszeit_nz_werkzeug_schliessen_s FLOAT,
                    zykluszeit_nz_duese_anlegen_s FLOAT,
                    zykluszeit_nz_einspritzen_s FLOAT,
                    zykluszeit_nz_werkzeug_oeffnen_s FLOAT,
                    zykluszeit_nz_auswerfen_s FLOAT,
                    zykluszeit_nz_kernzug_s FLOAT,
                    zykluszeit_nz_ausschrauben_s FLOAT,
                    zykluszeit_nz_einlegen_s FLOAT,
                    zykluszeit_nz_ausblasen_s FLOAT,
                    zykluszeit_temperaturleitfaehigkeit_m2_s FLOAT,
                    zykluszeit_optimale_kuehlzeit_s FLOAT,
                    zykluszeit_kuehlzeit_s FLOAT,
                    zykluszeit_nebenzeiten_gesamt_s FLOAT,
                    zykluszeit_vorschlag_s FLOAT,
                    zykluszeit_hinweis VARCHAR(512)
                )
                """
            )
        )


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_schema(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    now = datetime.now(timezone.utc).isoformat()
    session.execute(
        text(
            """
            INSERT INTO customers (id, customer_number, name, created_at, updated_at)
            VALUES (1, 'C1', 'Kunde', :now, :now)
            """
        ),
        {"now": now},
    )
    session.execute(
        text(
            """
            INSERT INTO programs (id, customer_id, program_number, name, created_at, updated_at)
            VALUES (1, 1, 'P1', 'Programm', :now, :now)
            """
        ),
        {"now": now},
    )
    session.execute(
        text(
            """
            INSERT INTO projects (id, program_id, project_number, name, created_at, updated_at)
            VALUES (10, 1, 'PR-A', 'Projekt A', :now, :now),
                   (20, 1, 'PR-B', 'Projekt B', :now, :now)
            """
        ),
        {"now": now},
    )
    session.execute(
        text(
            """
            INSERT INTO kaufteile (
                id, artikelnummer, bezeichnung, preis, project_id, aktiv, created_at, updated_at
            )
            VALUES
                (1, 'STD-1', 'Standard Clip', 0.5, NULL, 1, :now, :now),
                (2, 'A-1', 'Projekt A Clip', 1.0, 10, 1, :now, :now),
                (3, 'B-1', 'Projekt B Clip', 2.0, 20, 1, :now, :now),
                (4, 'A-IN', 'Inaktiv A', 1.5, 10, 0, :now, :now)
            """
        ),
        {"now": now},
    )
    session.commit()
    yield session
    session.close()


def test_list_project_includes_standard_by_default(db: Session) -> None:
    rows = list_kaufteile(
        skip=0,
        limit=100,
        nur_aktiv=False,
        customer_id=None,
        program_id=None,
        project_id=10,
        include_standard=True,
        strict_project=False,
        db=db,
        _=None,  # type: ignore[arg-type]
    )
    ids = {r.id for r in rows}
    assert ids == {1, 2, 4}


def test_list_strict_project_excludes_standard(db: Session) -> None:
    rows = list_kaufteile(
        skip=0,
        limit=100,
        nur_aktiv=False,
        customer_id=None,
        program_id=None,
        project_id=10,
        include_standard=False,
        strict_project=True,
        db=db,
        _=None,  # type: ignore[arg-type]
    )
    ids = {r.id for r in rows}
    assert ids == {2, 4}


def test_list_unfiltered_returns_all(db: Session) -> None:
    rows = list_kaufteile(
        skip=0,
        limit=100,
        nur_aktiv=False,
        customer_id=None,
        program_id=None,
        project_id=None,
        include_standard=True,
        strict_project=False,
        db=db,
        _=None,  # type: ignore[arg-type]
    )
    assert len(rows) == 4


def test_kaufteil_create_accepts_null_project_id() -> None:
    item = KaufteilCreate(
        artikelnummer="STD",
        bezeichnung="Standardteil",
        einheit="Stück",
        preis=0.1,
        nominierung="selbstnominiert",
        project_id=None,
    )
    assert item.project_id is None


def test_validate_accepts_standard_kaufteil(db: Session) -> None:
    class KaufteilRow:
        def __init__(self, row):
            self.id = row[0]
            self.bezeichnung = row[1]
            self.project_id = row[2]
            self.aktiv = bool(row[3])

    def patched_get(model, pk):
        if model is Kaufteil:
            row = db.execute(
                text("SELECT id, bezeichnung, project_id, aktiv FROM kaufteile WHERE id = :id"),
                {"id": pk},
            ).fetchone()
            return KaufteilRow(row) if row else None
        return None

    db.get = patched_get  # type: ignore[method-assign]

    _validate_zuordnungen_project_scope(
        db,
        10,
        [],
        [KaufteilZuordnungInput(kaufteil_id=1, menge=1, reihenfolge=1)],
    )


def test_validate_rejects_foreign_project_kaufteil(db: Session) -> None:
    class KaufteilRow:
        def __init__(self, row):
            self.id = row[0]
            self.bezeichnung = row[1]
            self.project_id = row[2]
            self.aktiv = bool(row[3])

    session = db
    session.get = lambda model, pk: (  # type: ignore[method-assign, assignment]
        KaufteilRow(
            session.execute(
                text("SELECT id, bezeichnung, project_id, aktiv FROM kaufteile WHERE id = :id"),
                {"id": pk},
            ).fetchone()
        )
        if model is Kaufteil
        else None
    )

    with pytest.raises(HTTPException) as exc:
        _validate_zuordnungen_project_scope(
            session,
            10,
            [],
            [KaufteilZuordnungInput(kaufteil_id=3, menge=1, reihenfolge=1)],
        )
    assert exc.value.status_code == 422

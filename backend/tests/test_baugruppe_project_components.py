"""Projektfilter für Baugruppen-Komponenten (Spritzguss/Kaufteile)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.baugruppen import _validate_zuordnungen_project_scope
from app.models.kaufteil import Kaufteil
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.schemas.baugruppe import KaufteilZuordnungInput, SpritzgussZuordnungInput
from app.services.spritzguss_cost_snapshot import (
    selbstkosten_aus_ergebnis,
    verkaufspreis_aus_ergebnis,
)


def _create_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
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
                    zykluszeit_groessenklasse VARCHAR(16),
                    zykluszeit_prozessaufwand VARCHAR(16),
                    zykluszeit_entnahmeart VARCHAR(16),
                    zykluszeit_kuehlzeit_s FLOAT,
                    zykluszeit_nebenzeiten_gesamt_s FLOAT,
                    zykluszeit_vorschlag_s FLOAT,
                    zykluszeit_hinweis VARCHAR(512),
                    teilbild_mime VARCHAR(64),
                    teilbild_data TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE kaufteile (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                    project_id INTEGER,
                    aktiv BOOLEAN NOT NULL DEFAULT 1
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
    session.execute(
        text(
            """
            INSERT INTO spritzguss_kalkulationen (id, teilebezeichnung, teilenummer, project_id, aktiv)
            VALUES
                (1, 'Teil A', 'A1', 10, 1),
                (2, 'Teil B', 'B1', 20, 1),
                (3, 'Global', 'G1', NULL, 1),
                (4, 'Inaktiv A', 'A2', 10, 0)
            """
        )
    )
    session.execute(
        text(
            """
            INSERT INTO kaufteile (id, bezeichnung, project_id, aktiv)
            VALUES (1, 'Clip A', 10, 1), (2, 'Clip B', 20, 1), (3, 'Standard Clip', NULL, 1)
            """
        )
    )
    session.commit()

    class SpritzgussRow:
        def __init__(self, row):
            self.id = row[0]
            self.teilebezeichnung = row[1]
            self.teilenummer = row[2]
            self.project_id = row[3]
            self.aktiv = bool(row[4])

    class KaufteilRow:
        def __init__(self, row):
            self.id = row[0]
            self.bezeichnung = row[1]
            self.project_id = row[2]
            self.aktiv = bool(row[3])

    def patched_get(model, pk):
        if model is SpritzgussKalkulation:
            row = session.execute(
                text(
                    "SELECT id, teilebezeichnung, teilenummer, project_id, aktiv "
                    "FROM spritzguss_kalkulationen WHERE id = :id"
                ),
                {"id": pk},
            ).fetchone()
            return SpritzgussRow(row) if row else None
        if model is Kaufteil:
            row = session.execute(
                text("SELECT id, bezeichnung, project_id, aktiv FROM kaufteile WHERE id = :id"),
                {"id": pk},
            ).fetchone()
            return KaufteilRow(row) if row else None
        return None

    session.get = patched_get  # type: ignore[method-assign]
    yield session
    session.close()


def test_validate_accepts_matching_project(db: Session) -> None:
    _validate_zuordnungen_project_scope(
        db,
        10,
        [SpritzgussZuordnungInput(spritzguss_kalkulation_id=1, menge=1, reihenfolge=1)],
        [KaufteilZuordnungInput(kaufteil_id=1, menge=1, reihenfolge=1)],
    )


def test_validate_accepts_standard_kaufteil(db: Session) -> None:
    _validate_zuordnungen_project_scope(
        db,
        10,
        [],
        [KaufteilZuordnungInput(kaufteil_id=3, menge=1, reihenfolge=1)],
    )


def test_validate_rejects_other_project(db: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_zuordnungen_project_scope(
            db,
            10,
            [SpritzgussZuordnungInput(spritzguss_kalkulation_id=2, menge=1, reihenfolge=1)],
            [],
        )
    assert exc.value.status_code == 422
    assert "Projekt" in str(exc.value.detail)


def test_validate_rejects_global_without_project(db: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_zuordnungen_project_scope(
            db,
            10,
            [SpritzgussZuordnungInput(spritzguss_kalkulation_id=3, menge=1, reihenfolge=1)],
            [],
        )
    assert exc.value.status_code == 422


def test_validate_allows_historical_inactive(db: Session) -> None:
    _validate_zuordnungen_project_scope(
        db,
        10,
        [SpritzgussZuordnungInput(spritzguss_kalkulation_id=4, menge=1, reihenfolge=1)],
        [],
        allow_inactive_spritzguss_ids={4},
    )


def test_validate_rejects_new_inactive(db: Session) -> None:
    with pytest.raises(HTTPException) as exc:
        _validate_zuordnungen_project_scope(
            db,
            10,
            [SpritzgussZuordnungInput(spritzguss_kalkulation_id=4, menge=1, reihenfolge=1)],
            [],
        )
    assert exc.value.status_code == 422
    assert "inaktiv" in str(exc.value.detail).lower()


def test_selbstkosten_helper_prefers_selbstkosten() -> None:
    assert selbstkosten_aus_ergebnis({"selbstkosten": 10.0, "verkaufspreis": 12.0}) == 10.0
    assert verkaufspreis_aus_ergebnis({"selbstkosten": 10.0, "endpreis_je_stueck": 12.0}) == 12.0

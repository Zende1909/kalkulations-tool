"""HTTP-Tests für POST /baugruppen/berechnen (Bumper-Fall, Fehlerbehandlung)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.core.security import UserRole
from app.database import get_db
from app.dependencies import get_current_user
from app.main import database_operational_error_handler

API = "/api/v1"


def _create_schema(engine, *, with_sga_columns: bool = True) -> None:
    sga_sql = ""
    if with_sga_columns:
        sga_sql = ", sga_override_aktiv BOOLEAN NOT NULL DEFAULT 0, sga_satz_manuell FLOAT"
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        conn.execute(
            text(
                """
                CREATE TABLE zuschlagssaetze (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                    satz_prozent FLOAT NOT NULL DEFAULT 0,
                    typ VARCHAR(64) NOT NULL,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        for typ, pct in (
            ("mgk_kaufteil_selbst", 3.0),
            ("mgk_kaufteil_oem", 5.0),
            ("fgk", 22.0),
            ("vvgk", 10.0),
            ("gewinn", 15.0),
            ("skonto", 0.0),
        ):
            conn.execute(
                text(
                    "INSERT INTO zuschlagssaetze (typ, bezeichnung, satz_prozent, aktiv) "
                    "VALUES (:typ, :typ, :pct, 1)"
                ),
                {"typ": typ, "pct": pct},
            )
        conn.execute(
            text(
                f"""
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    {sga_sql}
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO kaufteile (id, artikelnummer, bezeichnung, preis, nominierung, aktiv)
                VALUES (1, 'K-CLIP', 'Clip', 0.10, 'selbstnominiert', 1)
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
                    kunde VARCHAR(255) NOT NULL DEFAULT '',
                    projekt VARCHAR(255) NOT NULL DEFAULT '',
                    jahresstueckzahl INTEGER NOT NULL DEFAULT 0,
                    customer_id INTEGER,
                    program_id INTEGER,
                    project_id INTEGER,
                    calculation_year INTEGER,
                    project_volume FLOAT,
                    werk_id INTEGER,
                    losgroesse INTEGER,
                    losgroesse_modus VARCHAR(16),
                    losgroesse_manuell INTEGER,
                    material_id INTEGER,
                    schussgewicht_g FLOAT NOT NULL DEFAULT 0,
                    teilegewicht_netto_g FLOAT NOT NULL DEFAULT 100,
                    ausschussquote_pct FLOAT NOT NULL DEFAULT 0,
                    materialpreis_pro_kg FLOAT NOT NULL DEFAULT 0,
                    material_nominierung VARCHAR(32),
                    maschine_id INTEGER,
                    zykluszeit_s FLOAT NOT NULL DEFAULT 0,
                    kavitaeten INTEGER NOT NULL DEFAULT 1,
                    maschinenstundensatz FLOAT NOT NULL DEFAULT 0,
                    lohnkosten_id INTEGER,
                    lohnstundensatz FLOAT NOT NULL DEFAULT 0,
                    werkzeug_abrechnungsart VARCHAR(32) NOT NULL DEFAULT 'amortisation',
                    werkzeugkosten_eur FLOAT NOT NULL DEFAULT 0,
                    amortisationsvolumen INTEGER,
                    mgk_pct FLOAT NOT NULL DEFAULT 0,
                    fgk_pct FLOAT NOT NULL DEFAULT 0,
                    vvgk_pct FLOAT NOT NULL DEFAULT 0,
                    gewinn_pct FLOAT NOT NULL DEFAULT 0,
                    skonto_pct FLOAT NOT NULL DEFAULT 0,
                    ergebnis TEXT,
                    ergebnis_bloecke TEXT,
                    notizen TEXT NOT NULL DEFAULT '',
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
                    zykluszeit_hinweis VARCHAR(512),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO spritzguss_kalkulationen (id, teilebezeichnung, teilenummer, ergebnis)
                VALUES (1, 'Bumper', 'BMP-1', :ergebnis)
                """
            ),
            {"ergebnis": json.dumps({"selbstkosten": 19.39})},
        )
        conn.execute(
            text(
                """
                CREATE TABLE veredelungsschritte (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                    veredelungsart VARCHAR(64) NOT NULL DEFAULT 'Montage',
                    reihenfolge INTEGER NOT NULL DEFAULT 1,
                    beschreibung TEXT NOT NULL DEFAULT '',
                    taktzeit_s FLOAT NOT NULL DEFAULT 0,
                    anzahl_mitarbeiter INTEGER NOT NULL DEFAULT 1,
                    lohnkosten_id INTEGER,
                    lohnstundensatz FLOAT NOT NULL DEFAULT 0,
                    maschinenstundensatz FLOAT,
                    verbrauchskosten_je_stueck FLOAT NOT NULL DEFAULT 0,
                    ausschussquote_pct FLOAT NOT NULL DEFAULT 0,
                    fgk_pct FLOAT NOT NULL DEFAULT 0,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO veredelungsschritte (
                    id, bezeichnung, veredelungsart, taktzeit_s, anzahl_mitarbeiter,
                    lohnstundensatz, maschinenstundensatz, ausschussquote_pct
                ) VALUES (1, 'Montage', 'Montage', 500, 1, 12, 1.69, 1.5)
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE investitionen (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR(255) NOT NULL DEFAULT '',
                    investment_type VARCHAR(64) NOT NULL DEFAULT 'Werkzeug',
                    payment_type VARCHAR(64) NOT NULL DEFAULT 'Einmalzahlung',
                    amount FLOAT NOT NULL DEFAULT 0,
                    cost_amount FLOAT NOT NULL DEFAULT 0,
                    bottom_price FLOAT,
                    revenue_amount FLOAT,
                    amortization_volume INTEGER,
                    cost_per_piece FLOAT,
                    project_id VARCHAR(255) NOT NULL DEFAULT '',
                    customer VARCHAR(255) NOT NULL DEFAULT '',
                    part_name VARCHAR(255) NOT NULL DEFAULT '',
                    part_number VARCHAR(255) NOT NULL DEFAULT '',
                    calculation_id INTEGER,
                    baugruppe_id INTEGER,
                    supplier VARCHAR(255) NOT NULL DEFAULT '',
                    order_date DATE,
                    delivery_date DATE,
                    status VARCHAR(64) NOT NULL DEFAULT 'In Planung',
                    description TEXT NOT NULL DEFAULT '',
                    included_in_unit_price BOOLEAN NOT NULL DEFAULT 0,
                    archived BOOLEAN NOT NULL DEFAULT 0,
                    linked_project_id INTEGER,
                    customer_id INTEGER,
                    program_id INTEGER,
                    assignment_type VARCHAR(32),
                    kaufteil_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


def _client_for_session(db) -> TestClient:
    application = FastAPI()
    application.include_router(api_router)
    application.add_exception_handler(OperationalError, database_operational_error_handler)

    def override_get_db():
        yield db

    def override_current_user():
        return SimpleNamespace(
            email="kalkulator@example.com",
            role=UserRole.KALKULATOR.value,
            is_active=True,
        )

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_current_user] = override_current_user
    return TestClient(application)


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_schema(engine, with_sga_columns=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def client(db):
    with _client_for_session(db) as test_client:
        yield test_client


def _bumper_payload(*, snapshot_preis: float | None = 0.5665) -> dict:
    kt: dict = {"kaufteil_id": 1, "menge": 5, "reihenfolge": 2}
    if snapshot_preis is not None:
        kt["snapshot_preis"] = snapshot_preis
    return {
        "name": "Bumper",
        "jahresstueckzahl": 1000,
        "spritzguss_zuordnungen": [
            {"spritzguss_kalkulation_id": 1, "menge": 1, "reihenfolge": 1},
        ],
        "kaufteil_zuordnungen": [kt],
        "veredelung_zuordnungen": [
            {"veredelungsschritt_id": 1, "reihenfolge": 3, "mengenfaktor": 1},
        ],
    }


def test_berechnen_bumper_mit_frontend_snapshot_preis(client):
    """Frontend sendet snapshot_preis – Live-Berechnung nutzt Einkauf aus Stammdaten."""
    response = client.post(f"{API}/baugruppen/berechnen", json=_bumper_payload())
    assert response.status_code == 200, response.text
    endpreis = response.json()["ergebnis"]["baugruppenpreis_je_stueck"]
    assert endpreis == pytest.approx(26.0077397067, abs=0.01)


def test_berechnen_bumper_ohne_snapshot_preis(client):
    response = client.post(
        f"{API}/baugruppen/berechnen",
        json=_bumper_payload(snapshot_preis=None),
    )
    assert response.status_code == 200, response.text
    endpreis = response.json()["ergebnis"]["baugruppenpreis_je_stueck"]
    assert endpreis == pytest.approx(26.0077397067, abs=0.01)


def test_berechnen_fehlende_nominierung_422(client, db):
    db.execute(text("UPDATE kaufteile SET nominierung = NULL WHERE id = 1"))
    db.commit()
    response = client.post(
        f"{API}/baugruppen/berechnen",
        json=_bumper_payload(snapshot_preis=None),
    )
    assert response.status_code == 422, response.text
    assert "Nominierung" in response.json()["detail"]


def test_berechnen_pre_migration_kaufteil_schema_422():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_schema(engine, with_sga_columns=False)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    with _client_for_session(session) as test_client:
        response = test_client.post(
            f"{API}/baugruppen/berechnen",
            json=_bumper_payload(snapshot_preis=None),
        )
    assert response.status_code == 422, response.text
    assert "sga_override" in response.json()["detail"].lower() or "schema" in response.json()["detail"].lower()

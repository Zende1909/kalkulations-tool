"""Tests für Maschinengröße / Zuhaltekraft (Excel p1-1 ab AC27)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.spritzguss import _run_maschinen_groesse_for_request
from app.models.land import Land
from app.models.maschine import Maschine
from app.models.material import Material
from app.models.werk import Werk
from app.schemas.maschinen_groesse import MaschinenGroesseCalcRequest
from app.services.maschinen_groesse import (
    DEFAULT_INJECTION_PRESSURE_KG_CM2,
    MaschinenGroesseInput,
    MaschinenGroesseValidationError,
    SAFETY_FACTOR,
    berechne_maschinen_groesse,
    berechne_maschinen_groesse_mit_auswahl,
    validate_injection_pressure,
    zuhaltekraft_aus_flaeche,
    zuhaltekraft_aus_masse,
)


def _machine_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE laender (
                    id INTEGER PRIMARY KEY,
                    code VARCHAR(16) NOT NULL UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP, updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE werke (
                    id INTEGER PRIMARY KEY,
                    land_id INTEGER NOT NULL REFERENCES laender(id),
                    code VARCHAR(32) NOT NULL UNIQUE,
                    name VARCHAR(255) NOT NULL,
                    currency VARCHAR(8) NOT NULL DEFAULT 'EUR',
                    fx_to_eur FLOAT NOT NULL DEFAULT 1.0,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    arbeitstage_pro_jahr FLOAT,
                    produktionsintervall_arbeitstage FLOAT,
                    schichten_pro_tag FLOAT,
                    stunden_pro_schicht FLOAT,
                    oee FLOAT,
                    space_cost_satz_pro_sqm_jahr FLOAT,
                    abschreibungsdauer_jahre FLOAT,
                    zinssatz FLOAT,
                    versicherungssatz FLOAT,
                    instandhaltungssatz FLOAT,
                    strompreis FLOAT,
                    druckluftpreis FLOAT,
                    kuehlwasserpreis FLOAT,
                    created_at TIMESTAMP, updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE materialien (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL,
                    material_nr VARCHAR(100) NOT NULL UNIQUE,
                    preis_pro_kg FLOAT NOT NULL DEFAULT 0,
                    dichte FLOAT NOT NULL DEFAULT 0,
                    waehrung VARCHAR(8) NOT NULL DEFAULT 'EUR',
                    injection_pressure_kg_cm2 FLOAT NOT NULL DEFAULT 500,
                    materialgruppe VARCHAR(32),
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP, updated_at TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE maschinen (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL,
                    maschinen_nr VARCHAR(50) NOT NULL UNIQUE,
                    stundensatz FLOAT NOT NULL DEFAULT 0,
                    schliesskraft_t FLOAT NOT NULL DEFAULT 0,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    werk_id INTEGER REFERENCES werke(id),
                    maschinentyp VARCHAR(128),
                    variante VARCHAR(64),
                    source_currency VARCHAR(8),
                    arbeitstage_pro_jahr FLOAT,
                    schichten_pro_tag FLOAT,
                    stunden_pro_schicht FLOAT,
                    oee FLOAT,
                    investment FLOAT,
                    flaeche_sqm FLOAT,
                    space_cost_satz_pro_sqm_jahr FLOAT,
                    abschreibungsdauer_jahre FLOAT,
                    zinssatz FLOAT,
                    versicherungssatz FLOAT,
                    instandhaltungssatz FLOAT,
                    stromverbrauch_kwh_h FLOAT,
                    strompreis FLOAT,
                    druckluftverbrauch_m3_h FLOAT,
                    druckluftpreis FLOAT,
                    kuehlwasserverbrauch_m3_h FLOAT,
                    kuehlwasserpreis FLOAT,
                    setup_zeit_min FLOAT,
                    setup_mitarbeiter FLOAT,
                    jahresstunden FLOAT,
                    space_costs_pro_stunde FLOAT,
                    abschreibung_pro_stunde FLOAT,
                    zinsen_pro_stunde FLOAT,
                    versicherung_pro_stunde FLOAT,
                    instandhaltung_pro_stunde FLOAT,
                    energie_pro_stunde FLOAT,
                    stundensatz_source FLOAT,
                    rate_updated_at TIMESTAMP,
                    created_at TIMESTAMP, updated_at TIMESTAMP
                )
                """
            )
        )


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _machine_schema(engine)
    factory = sessionmaker(bind=engine)
    session = factory()
    try:
        yield session
    finally:
        session.close()


def test_material_default_injection_pressure_500():
    mat = Material(
        bezeichnung="PP Test",
        material_nr="PP-001",
        preis_pro_kg=2.0,
        dichte=1.0,
        injection_pressure_kg_cm2=DEFAULT_INJECTION_PRESSURE_KG_CM2,
    )
    assert mat.injection_pressure_kg_cm2 == 500.0


def test_validate_injection_pressure_rejects_missing():
    with pytest.raises(MaschinenGroesseValidationError, match="fehlt"):
        validate_injection_pressure(None)


def test_validate_injection_pressure_rejects_invalid():
    with pytest.raises(MaschinenGroesseValidationError, match="größer als 0"):
        validate_injection_pressure(0)


def test_masse_excel_example_ad35():
    """Excel p1-1: Width 1751, Length 555, Openings 35 %, Pressure 500, Cavities 1."""
    netto, ohne = zuhaltekraft_aus_masse(
        breite_mm=1751,
        laenge_mm=555,
        oeffnungen_pct=35,
        injection_pressure_kg_cm2=500,
        kavitaeten=1,
    )
    expected_netto = 1751 * 555 * (1 - 35 / 100)
    expected_ohne = expected_netto / 100 * 500 * 1 / 1000
    assert netto == expected_netto
    assert ohne == expected_ohne
    assert ohne * SAFETY_FACTOR == pytest.approx(expected_ohne * 1.2)


def test_flaeche_excel_example_ag33():
    """Excel p1-1: Proj. Surface 631653 mm², Pressure 500, Cavities 1."""
    netto, ohne = zuhaltekraft_aus_flaeche(
        proj_flaeche_mm2=631653,
        injection_pressure_kg_cm2=500,
        kavitaeten=1,
    )
    expected_netto = 631653
    expected_ohne = expected_netto / 100 * 500 / 1000
    assert netto == expected_netto
    assert ohne == expected_ohne


def test_safety_factor_20_percent():
    result = berechne_maschinen_groesse(
        MaschinenGroesseInput(
            modus="flaeche",
            proj_flaeche_mm2=100000,
            injection_pressure_kg_cm2=400,
            kavitaeten=2,
        )
    )
    assert result.sicherheitszuschlag_faktor == 1.2
    assert result.zuhaltekraft_erforderlich_t == result.zuhaltekraft_ohne_sicherheit_t * 1.2


def test_waehle_kleinste_passende_maschine(db: Session):
    land = Land(code="DE", name="Deutschland", aktiv=True)
    db.add(land)
    db.flush()
    werk = Werk(land_id=land.id, code="W1", name="Werk 1", currency="EUR", fx_to_eur=1.0, aktiv=True)
    db.add(werk)
    db.flush()
    db.add_all(
        [
            Maschine(
                bezeichnung="Klein",
                maschinen_nr="M-100",
                stundensatz=50,
                schliesskraft_t=100,
                werk_id=werk.id,
                maschinentyp="Spritzguss",
                aktiv=True,
            ),
            Maschine(
                bezeichnung="Groß",
                maschinen_nr="M-500",
                stundensatz=80,
                schliesskraft_t=500,
                werk_id=werk.id,
                maschinentyp="Spritzguss",
                aktiv=True,
            ),
            Maschine(
                bezeichnung="Veredelung",
                maschinen_nr="V-1",
                stundensatz=30,
                schliesskraft_t=1000,
                werk_id=werk.id,
                maschinentyp="Veredelung",
                aktiv=True,
            ),
        ]
    )
    db.commit()

    result = berechne_maschinen_groesse_mit_auswahl(
        db,
        MaschinenGroesseInput(
            modus="flaeche",
            proj_flaeche_mm2=10000,
            injection_pressure_kg_cm2=500,
            kavitaeten=1,
        ),
        werk_id=werk.id,
    )
    assert result.empfohlene_maschine_id is not None
    maschine = db.get(Maschine, result.empfohlene_maschine_id)
    assert maschine is not None
    assert maschine.maschinen_nr == "M-100"


def test_kavitaeten_1_vs_4_unterschiedliche_zuhaltekraft():
    base = berechne_maschinen_groesse(
        MaschinenGroesseInput(
            modus="flaeche",
            proj_flaeche_mm2=100000,
            injection_pressure_kg_cm2=500,
            kavitaeten=1,
        )
    )
    vier = berechne_maschinen_groesse(
        MaschinenGroesseInput(
            modus="flaeche",
            proj_flaeche_mm2=100000,
            injection_pressure_kg_cm2=500,
            kavitaeten=4,
        )
    )
    assert vier.zuhaltekraft_ohne_sicherheit_t == base.zuhaltekraft_ohne_sicherheit_t * 4
    assert vier.kavitaeten == 4


def test_keine_passende_maschine_warnung_text(db: Session):
    land = Land(code="DE", name="Deutschland", aktiv=True)
    db.add(land)
    db.flush()
    werk = Werk(land_id=land.id, code="W1", name="Werk 1", currency="EUR", fx_to_eur=1.0, aktiv=True)
    db.add(werk)
    db.flush()
    db.add(
        Maschine(
            bezeichnung="Klein",
            maschinen_nr="M-10",
            stundensatz=50,
            schliesskraft_t=10,
            werk_id=werk.id,
            maschinentyp="Spritzguss",
            aktiv=True,
        )
    )
    db.commit()

    result = berechne_maschinen_groesse_mit_auswahl(
        db,
        MaschinenGroesseInput(
            modus="masse",
            breite_mm=5000,
            laenge_mm=5000,
            oeffnungen_pct=0,
            injection_pressure_kg_cm2=500,
            kavitaeten=4,
        ),
        werk_id=werk.id,
    )
    assert result.empfohlene_maschine_id is None
    assert result.warnung == "Keine passende Maschine"


def test_api_preview_uses_kavitaeten_and_recommends_machine(db: Session):
    land = Land(code="DE", name="Deutschland", aktiv=True)
    db.add(land)
    db.flush()
    werk = Werk(land_id=land.id, code="W1", name="Werk 1", currency="EUR", fx_to_eur=1.0, aktiv=True)
    db.add(werk)
    db.flush()
    material = Material(
        bezeichnung="PP",
        material_nr="PP-1",
        preis_pro_kg=2.0,
        dichte=1.0,
        injection_pressure_kg_cm2=500,
        aktiv=True,
    )
    db.add(material)
    db.add(
        Maschine(
            bezeichnung="Klein",
            maschinen_nr="M-100",
            stundensatz=50,
            schliesskraft_t=100,
            werk_id=werk.id,
            maschinentyp="Spritzguss",
            aktiv=True,
        )
    )
    db.commit()

    result = _run_maschinen_groesse_for_request(
        db,
        MaschinenGroesseCalcRequest(
            maschinen_groesse_modus="flaeche",
            maschinen_groesse_proj_flaeche_mm2=1000,
            material_id=material.id,
            kavitaeten=4,
            werk_id=werk.id,
        ),
        werk_id=werk.id,
    )
    assert result is not None
    assert result.kavitaeten == 4
    assert result.empfohlene_maschine_id is not None


def test_invalid_masse_input():
    with pytest.raises(MaschinenGroesseValidationError):
        berechne_maschinen_groesse(
            MaschinenGroesseInput(
                modus="masse",
                breite_mm=None,
                laenge_mm=100,
                oeffnungen_pct=10,
                injection_pressure_kg_cm2=500,
                kavitaeten=1,
            )
        )

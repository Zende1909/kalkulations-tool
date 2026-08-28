"""Regression: automatische Losgröße über Produktionsintervall (30 Arbeitstage)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import spritzguss as spritzguss_api
from app.services.losgroesse_berechnung import (
    DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE,
    LosgroesseValidationError,
    berechne_automatische_losgroesse,
    resolve_losgroesse,
    werk_produktionsintervall,
)
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss
from app.services.project_volume_service import AverageJahresstueckzahl


def test_standard_produktionsintervall_ist_30():
    assert DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE == 30


def test_formel_20000_254_30():
    r = berechne_automatische_losgroesse(20_000, 30, 254)
    assert r.raw_vor_ceil == pytest.approx(2362.204724, rel=1e-6)
    assert r.automatische_losgroesse == 2363


def test_formel_41875_254_30():
    r = berechne_automatische_losgroesse(41_875, 30, 254)
    assert r.raw_vor_ceil == pytest.approx(4945.866141, rel=1e-6)
    assert r.automatische_losgroesse == 4946


def test_mindestens_1():
    r = berechne_automatische_losgroesse(1, 30, 254)
    assert r.automatische_losgroesse == 1


def test_hoechstens_jahresbedarf():
    r = berechne_automatische_losgroesse(100, 30, 254)
    assert r.automatische_losgroesse <= 100


def test_jahresbedarf_kleiner_als_1_ergibt_1():
    r = berechne_automatische_losgroesse(1, 30, 254)
    assert r.automatische_losgroesse == 1


def test_fehlender_jahresbedarf():
    with pytest.raises(LosgroesseValidationError, match="Jahresbedarf"):
        berechne_automatische_losgroesse(0, 30, 254)


def test_jahresbedarf_null():
    with pytest.raises(LosgroesseValidationError):
        berechne_automatische_losgroesse(0, 30, 254)


def test_fehlende_arbeitstage():
    with pytest.raises(LosgroesseValidationError, match="Arbeitstage"):
        berechne_automatische_losgroesse(20_000, 30, 0)


def test_arbeitstage_null():
    with pytest.raises(LosgroesseValidationError):
        berechne_automatische_losgroesse(20_000, 30, 0)


def test_ungueltiges_produktionsintervall():
    with pytest.raises(LosgroesseValidationError, match="Produktionsintervall"):
        berechne_automatische_losgroesse(20_000, 0, 254)


def test_werk_default_intervall_30():
    assert werk_produktionsintervall(None) == 30


def test_intervall_30_reduziert_setup_gegenueber_10():
    base = dict(
        teilegewicht_netto_g=100.0,
        schussgewicht_g=120.0,
        materialpreis_pro_kg=10.0,
        ausschussquote_pct=1.0,
        mgk_pct=3.0,
        zykluszeit_s=60.0,
        maschinenstundensatz=40.0,
        kavitaeten=1,
        lohnstundensatz=12.0,
        fgk_pct=22.0,
        werkzeugkosten_eur=0,
        setup_aktiv=True,
        setup_zeit_min=60.0,
        setup_maschinenstundensatz=40.0,
        setup_lohnstundensatz=25.0,
        setup_mitarbeiter=1.0,
    )
    los_10 = berechne_automatische_losgroesse(20_000, 10, 254).automatische_losgroesse
    los_30 = berechne_automatische_losgroesse(20_000, 30, 254).automatische_losgroesse
    assert los_30 > los_10
    s10 = berechne_spritzguss(SpritzgussInput(**base, losgroesse=los_10))
    s30 = berechne_spritzguss(SpritzgussInput(**base, losgroesse=los_30))
    assert s30.setup_kosten_je_teil < s10.setup_kosten_je_teil


def test_setup_maschine_und_lohn_getrennt():
    sg = berechne_spritzguss(
        SpritzgussInput(
            teilegewicht_netto_g=100.0,
            schussgewicht_g=120.0,
            materialpreis_pro_kg=10.0,
            ausschussquote_pct=0.0,
            mgk_pct=0.0,
            zykluszeit_s=60.0,
            maschinenstundensatz=40.0,
            kavitaeten=1,
            lohnstundensatz=12.0,
            fgk_pct=22.0,
            werkzeugkosten_eur=0,
            setup_aktiv=True,
            setup_zeit_min=60.0,
            setup_maschinenstundensatz=100.0,
            setup_lohnstundensatz=50.0,
            setup_mitarbeiter=2.0,
            losgroesse=100,
        )
    )
    assert sg.setup_maschinenkosten_je_teil > 0
    assert sg.setup_lohnkosten_je_teil > 0
    assert sg.setup_kosten_je_teil == pytest.approx(
        sg.setup_maschinenkosten_je_teil + sg.setup_lohnkosten_je_teil
    )


def _session_with_project_volume(jahresbedarf: int = 20_000) -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE laender (id INTEGER PRIMARY KEY, code VARCHAR(16), name VARCHAR(255), aktiv BOOLEAN DEFAULT 1)"))
        conn.execute(text("CREATE TABLE werke (id INTEGER PRIMARY KEY, land_id INTEGER, code VARCHAR(32), name VARCHAR(255), currency VARCHAR(8), fx_to_eur FLOAT, aktiv BOOLEAN DEFAULT 1, arbeitstage_pro_jahr FLOAT, produktionsintervall_arbeitstage FLOAT, schichten_pro_tag FLOAT, stunden_pro_schicht FLOAT, oee FLOAT, space_cost_satz_pro_sqm_jahr FLOAT, abschreibungsdauer_jahre FLOAT, zinssatz FLOAT, versicherungssatz FLOAT, instandhaltungssatz FLOAT, strompreis FLOAT, druckluftpreis FLOAT, kuehlwasserpreis FLOAT, created_at TIMESTAMP, updated_at TIMESTAMP)"))
        conn.execute(text("CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(255))"))
        conn.execute(text("CREATE TABLE programs (id INTEGER PRIMARY KEY, customer_id INTEGER, name VARCHAR(255))"))
        conn.execute(text("CREATE TABLE projects (id INTEGER PRIMARY KEY, program_id INTEGER, name VARCHAR(255), quantity_per_vehicle FLOAT DEFAULT 1)"))
        conn.execute(text("CREATE TABLE program_volumes (id INTEGER PRIMARY KEY, program_id INTEGER, calendar_year INTEGER, vehicle_volume INTEGER)"))
        conn.execute(text("INSERT INTO laender (id, code, name) VALUES (1, 'DE', 'Deutschland')"))
        conn.execute(text("INSERT INTO werke (id, land_id, code, name, currency, fx_to_eur, arbeitstage_pro_jahr, produktionsintervall_arbeitstage) VALUES (1, 1, 'KAEC', 'KAEC', 'EUR', 1.0, 254, 30)"))
        conn.execute(text("INSERT INTO customers (id, name) VALUES (1, 'K')"))
        conn.execute(text("INSERT INTO programs (id, customer_id, name) VALUES (1, 1, 'P')"))
        conn.execute(text("INSERT INTO projects (id, program_id, name, quantity_per_vehicle) VALUES (1, 1, 'Pr', 1)"))
        conn.execute(text("INSERT INTO program_volumes (id, program_id, calendar_year, vehicle_volume) VALUES (1, 1, 2025, :v)"), {"v": jahresbedarf})
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_resolve_automatisch_mit_projekt_und_werk(monkeypatch):
    db = _session_with_project_volume(20_000)
    try:
        monkeypatch.setattr(
            "app.services.losgroesse_berechnung.average_jahresstueckzahl_for_project",
            lambda _db, _pid: AverageJahresstueckzahl(
                project_id=1,
                year_count=1,
                sum_project_volume=20_000.0,
                average_raw=20_000.0,
                jahresstueckzahl=20_000,
                has_volumes=True,
            ),
        )
        ctx = resolve_losgroesse(
            db,
            modus="automatisch",
            losgroesse_manuell=None,
            losgroesse_gespeichert=None,
            project_id=1,
            werk_id=1,
            setup_aktiv=True,
        )
        assert ctx.losgroesse_aktiv == 2363
        assert ctx.modus == "automatisch"
    finally:
        db.close()


def test_manuelle_losgroesse_hat_vorrang(monkeypatch):
    db = _session_with_project_volume(20_000)
    try:
        monkeypatch.setattr(
            "app.services.losgroesse_berechnung.average_jahresstueckzahl_for_project",
            lambda _db, _pid: AverageJahresstueckzahl(
                project_id=1,
                year_count=1,
                sum_project_volume=20_000.0,
                average_raw=20_000.0,
                jahresstueckzahl=20_000,
                has_volumes=True,
            ),
        )
        ctx = resolve_losgroesse(
            db,
            modus="manuell",
            losgroesse_manuell=500,
            losgroesse_gespeichert=None,
            project_id=1,
            werk_id=1,
            setup_aktiv=True,
        )
        assert ctx.losgroesse_aktiv == 500
        assert ctx.losgroesse_automatisch == 2363
    finally:
        db.close()


def test_manuelle_dezimalwerte_abgelehnt():
    from pydantic import ValidationError

    from app.schemas.spritzguss_kalkulation import SpritzgussCalcRequest

    with pytest.raises(ValidationError):
        SpritzgussCalcRequest(
            teilegewicht_netto_g=100.0,
            schussgewicht_g=120.0,
            materialpreis_pro_kg=10.0,
            ausschussquote_pct=0.0,
            zykluszeit_s=60.0,
            maschinenstundensatz=40.0,
            kavitaeten=1,
            lohnstundensatz=12.0,
            werkzeugkosten_eur=0,
            losgroesse_modus="manuell",
            losgroesse_manuell=100.5,
        )


def test_api_berechnen_automatische_losgroesse(monkeypatch):
    from app.schemas.spritzguss_kalkulation import SpritzgussCalcRequest

    db = _session_with_project_volume(20_000)
    monkeypatch.setattr(
        "app.services.losgroesse_berechnung.average_jahresstueckzahl_for_project",
        lambda _db, _pid: AverageJahresstueckzahl(
            project_id=1,
            year_count=1,
            sum_project_volume=20_000.0,
            average_raw=20_000.0,
            jahresstueckzahl=20_000,
            has_volumes=True,
        ),
    )
    monkeypatch.setattr(
        "app.api.v1.spritzguss.load_central_markup_rates",
        lambda _db, werk_id=None: type(
            "Rates",
            (),
            {
                "mgk_pct_for_nominierung": lambda self, *a, **k: 3.0,
                "fgk_pct": 22.0,
                "vvgk_pct": 10.0,
                "gewinn_pct": 15.0,
                "skonto_pct": 0.0,
            },
        )(),
    )
    try:
        calc_req = SpritzgussCalcRequest(
            teilegewicht_netto_g=996.0,
            schussgewicht_g=2100.0,
            materialpreis_pro_kg=10.0,
            ausschussquote_pct=1.0,
            zykluszeit_s=500.0,
            maschinenstundensatz=40.0,
            kavitaeten=2,
            lohnstundensatz=12.0,
            werkzeugkosten_eur=0,
            werkzeug_abrechnungsart="einmalzahlung",
            setup_aktiv=True,
            setup_zeit_min=80.0,
            setup_maschinenstundensatz=40.0,
            setup_lohnstundensatz=25.0,
            setup_mitarbeiter=1.5,
            project_id=1,
            werk_id=1,
            losgroesse_modus="automatisch",
        )
        berechnet = spritzguss_api._run_calculation(
            db,
            spritzguss_api._to_calc_input_from_request(calc_req),
            [],
            werk_id=1,
            project_id=1,
            losgroesse_modus="automatisch",
        )
        assert berechnet.ergebnis.losgroesse_aktiv == 2363
        assert berechnet.ergebnis.losgroesse_modus == "automatisch"
    finally:
        db.close()

"""Regression: Armlehne – Berechnen und Speichern liefern denselben Endpreis.

Ursache (vor dem Fix): Save-Pfad nutzte Veredelungs-Snapshots nur mit
``kosten_inkl_ausschuss`` und ohne ``kosten_vor_ausschuss`` / Ausschussquote.
Damit fiel ``berechne_gesamt`` auf die Legacy-Addition ohne Vorprodukt-Kaskade;
„Berechnen“ (live) wendete die Ausbeutekette an → Endpreis-Abweichung.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import spritzguss as spritzguss_api
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.models.veredelungsschritt import Veredelungsschritt
from app.schemas.spritzguss_veredelung import VeredelungZuordnungInput
from app.scripts.seed_top_level_markup_rates import seed_top_level_markup_rates
from app.services.spritzguss_gesamt_kalkulation import (
    VeredelungSchrittEingabe,
    berechne_gesamt,
)
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss
from app.services.veredelung_kalkulation import VeredelungInput, berechne_veredelung


# Pilotfall Armlehne (TSV) + Kaschieren
ARMLEHNE_SG = dict(
    schussgewicht_g=200.0,
    teilegewicht_netto_g=200.0,
    materialpreis_pro_kg=8.0,
    ausschussquote_pct=2.5,
    mgk_pct=3.0,
    material_nominierung="selbstnominiert",
    zykluszeit_s=40.0,
    maschinenstundensatz=80.0,
    kavitaeten=1,
    lohnstundensatz=40.0,
    fgk_pct=22.0,
    werkzeugkosten_eur=0,
    werkzeug_abrechnungsart="einmalzahlung",
    amortisationsvolumen=None,
    vvgk_pct=10.0,
    gewinn_pct=15.0,
    skonto_pct=0.0,
)

KASCHIEREN = dict(
    taktzeit_s=36.0,
    anzahl_mitarbeiter=1,
    lohnstundensatz=50.0,
    maschinenstundensatz=100.0,
    verbrauchskosten_je_stueck=0.5,
    ausschussquote_pct=1.5,
    fgk_pct=0,
    reihenfolge=1,
)

RATES = dict(fgk_pct=22.0, vvgk_pct=10.0, gewinn_pct=15.0, skonto_pct=0.0)

COMPARE_KEYS = (
    "materialkosten_gesamt",
    "fertigungsgemeinkosten",
    "fgk_basis",
    "veredelung_gesamt",
    "vvgk",
    "gewinn",
    "skonto",
    "endpreis_je_stueck",
)


def _armlehne_sg_dict() -> dict:
    return berechne_spritzguss(SpritzgussInput(**ARMLEHNE_SG)).to_dict()


def _kasch_live():
    return berechne_veredelung(VeredelungInput(**KASCHIEREN))


def test_armlehne_snapshot_ohne_vor_kosten_weicht_ab():
    """Dokumentiert die historische Bug-Ursache (Legacy-Additiv vs. Kaskade)."""
    sg = _armlehne_sg_dict()
    kasch = _kasch_live()
    live = berechne_gesamt(
        sg,
        [
            VeredelungSchrittEingabe(
                veredelungsschritt_id=1,
                bezeichnung="Kaschieren TPO",
                veredelungsart="Kaschieren",
                reihenfolge=1,
                aktiv=True,
                mengenfaktor=1.0,
                kosten_inkl_ausschuss=kasch.kosten_inkl_ausschuss,
                kosten_vor_ausschuss=kasch.kosten_vor_ausschuss,
                ausschussquote_pct=1.5,
            )
        ],
        **RATES,
    )
    legacy = berechne_gesamt(
        sg,
        [
            VeredelungSchrittEingabe(
                veredelungsschritt_id=1,
                bezeichnung="Kaschieren TPO",
                veredelungsart="Kaschieren",
                reihenfolge=1,
                aktiv=True,
                mengenfaktor=1.0,
                kosten_inkl_ausschuss=kasch.kosten_inkl_ausschuss,
                kosten_vor_ausschuss=None,
                ausschussquote_pct=0.0,
            )
        ],
        **RATES,
    )
    assert live.endpreis_je_stueck == pytest.approx(7.44)
    assert legacy.endpreis_je_stueck == pytest.approx(7.38)
    assert live.endpreis_je_stueck != legacy.endpreis_je_stueck


def test_armlehne_snapshot_mit_vor_kosten_gleich_berechnen():
    sg = _armlehne_sg_dict()
    kasch = _kasch_live()
    live = berechne_gesamt(
        sg,
        [
            VeredelungSchrittEingabe(
                veredelungsschritt_id=1,
                bezeichnung="Kaschieren TPO",
                veredelungsart="Kaschieren",
                reihenfolge=1,
                aktiv=True,
                mengenfaktor=1.0,
                kosten_inkl_ausschuss=kasch.kosten_inkl_ausschuss,
                kosten_vor_ausschuss=kasch.kosten_vor_ausschuss,
                ausschussquote_pct=1.5,
            )
        ],
        **RATES,
    )
    snap = berechne_gesamt(
        sg,
        [
            VeredelungSchrittEingabe(
                veredelungsschritt_id=1,
                bezeichnung="Kaschieren TPO",
                veredelungsart="Kaschieren",
                reihenfolge=1,
                aktiv=True,
                mengenfaktor=1.0,
                kosten_inkl_ausschuss=kasch.kosten_inkl_ausschuss,
                kosten_vor_ausschuss=kasch.kosten_vor_ausschuss,
                ausschussquote_pct=1.5,
            )
        ],
        **RATES,
    )
    for key in COMPARE_KEYS:
        assert getattr(snap, key) == pytest.approx(getattr(live, key)), key


def _session_with_schema() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE zuschlagssaetze (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL,
                    satz_prozent FLOAT NOT NULL,
                    typ VARCHAR(50) NOT NULL,
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
                CREATE TABLE veredelungsschritte (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL,
                    veredelungsart VARCHAR(64) NOT NULL DEFAULT '',
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
                    losgroesse INTEGER, losgroesse_modus VARCHAR(16), losgroesse_manuell INTEGER,
                    material_id INTEGER,
                    schussgewicht_g FLOAT NOT NULL DEFAULT 0,
                    teilegewicht_netto_g FLOAT NOT NULL DEFAULT 0,
                    ausschussquote_pct FLOAT NOT NULL DEFAULT 0,
                    materialpreis_pro_kg FLOAT NOT NULL DEFAULT 0,
                    material_nominierung VARCHAR(32),
                    maschine_id INTEGER,
                    zykluszeit_s FLOAT NOT NULL DEFAULT 0,
                    kavitaeten INTEGER NOT NULL DEFAULT 1,
                    maschinenstundensatz FLOAT NOT NULL DEFAULT 0,
                    lohnkosten_id INTEGER,
                    lohnstundensatz FLOAT NOT NULL DEFAULT 0,
                    werkzeug_abrechnungsart VARCHAR(32) NOT NULL DEFAULT 'einmalzahlung',
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE spritzguss_veredelung_zuordnungen (
                    id INTEGER PRIMARY KEY,
                    kalkulation_id INTEGER NOT NULL
                        REFERENCES spritzguss_kalkulationen(id) ON DELETE CASCADE,
                    veredelungsschritt_id INTEGER NOT NULL,
                    reihenfolge INTEGER NOT NULL DEFAULT 1,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    mengenfaktor FLOAT NOT NULL DEFAULT 1,
                    snapshot_bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                    snapshot_veredelungsart VARCHAR(64) NOT NULL DEFAULT '',
                    snapshot_kosten_inkl_ausschuss FLOAT NOT NULL DEFAULT 0,
                    snapshot_kosten_vor_ausschuss FLOAT,
                    snapshot_ausschussquote_pct FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    return SessionLocal()


def _add_kaschieren(db: Session) -> Veredelungsschritt:
    schritt = Veredelungsschritt(
        id=1,
        bezeichnung="Kaschieren TPO",
        veredelungsart="Kaschieren",
        taktzeit_s=KASCHIEREN["taktzeit_s"],
        anzahl_mitarbeiter=int(KASCHIEREN["anzahl_mitarbeiter"]),
        lohnstundensatz=KASCHIEREN["lohnstundensatz"],
        maschinenstundensatz=KASCHIEREN["maschinenstundensatz"],
        verbrauchskosten_je_stueck=KASCHIEREN["verbrauchskosten_je_stueck"],
        ausschussquote_pct=KASCHIEREN["ausschussquote_pct"],
        fgk_pct=0,
        reihenfolge=1,
        aktiv=True,
    )
    db.add(schritt)
    db.commit()
    return schritt


def test_armlehne_berechnen_speichern_reload_identisch():
    """1–4: Berechnen == Speichern == Reload; Detailwerte gleich. 5: Eingabeänderung."""
    db = _session_with_schema()
    try:
        seed_top_level_markup_rates(db)
        _add_kaschieren(db)
        kasch = _kasch_live()

        zuordnungen = [
            VeredelungZuordnungInput(
                veredelungsschritt_id=1,
                reihenfolge=1,
                aktiv=True,
                mengenfaktor=1.0,
            )
        ]
        calc_input = SpritzgussInput(**ARMLEHNE_SG)

        berechnet = spritzguss_api._build_calc_response(
            db, calc_input, zuordnungen, use_snapshots=False
        )
        assert berechnet.ergebnis.endpreis_je_stueck == pytest.approx(7.44)

        obj = SpritzgussKalkulation(
            teilebezeichnung="Armlehne",
            teilenummer="ARM-1",
            schussgewicht_g=200.0,
            teilegewicht_netto_g=200.0,
            materialpreis_pro_kg=8.0,
            ausschussquote_pct=2.5,
            mgk_pct=3.0,
            material_nominierung="selbstnominiert",
            zykluszeit_s=40.0,
            maschinenstundensatz=80.0,
            kavitaeten=1,
            lohnstundensatz=40.0,
            fgk_pct=22.0,
            werkzeugkosten_eur=0,
            werkzeug_abrechnungsart="einmalzahlung",
            amortisationsvolumen=None,
            vvgk_pct=10.0,
            gewinn_pct=15.0,
            skonto_pct=0.0,
        )
        db.add(obj)
        db.flush()
        spritzguss_api._sync_veredelung_zuordnungen(db, obj, zuordnungen)
        gespeichert = spritzguss_api._apply_calculation(
            db, obj, zuordnungen, use_snapshots=True
        )
        db.commit()
        db.refresh(obj)

        assert gespeichert.ergebnis.endpreis_je_stueck == pytest.approx(
            berechnet.ergebnis.endpreis_je_stueck
        )
        berechnet_dump = berechnet.ergebnis.model_dump()
        for key in COMPARE_KEYS:
            assert getattr(gespeichert.ergebnis, key) == pytest.approx(
                getattr(berechnet.ergebnis, key)
            ), key
            stored = obj.ergebnis[key] if isinstance(obj.ergebnis, dict) else None
            assert stored == pytest.approx(berechnet_dump[key]), f"stored.{key}"

        snap_row = db.scalars(select(SpritzgussVeredelungZuordnung)).one()
        assert snap_row.snapshot_kosten_vor_ausschuss == pytest.approx(
            kasch.kosten_vor_ausschuss
        )
        assert snap_row.snapshot_ausschussquote_pct == pytest.approx(1.5)

        geladen = spritzguss_api._kalkulation_to_read(db, obj)
        assert geladen.ergebnis["endpreis_je_stueck"] == pytest.approx(
            berechnet.ergebnis.endpreis_je_stueck
        )

        erneut = spritzguss_api._build_calc_response(
            db,
            spritzguss_api._to_calc_input_from_model(obj),
            zuordnungen,
            use_snapshots=False,
        )
        assert erneut.ergebnis.endpreis_je_stueck == pytest.approx(
            berechnet.ergebnis.endpreis_je_stueck
        )

        geaendert = SpritzgussInput(**{**ARMLEHNE_SG, "schussgewicht_g": 220.0})
        neu = spritzguss_api._build_calc_response(
            db, geaendert, zuordnungen, use_snapshots=False
        )
        assert neu.ergebnis.endpreis_je_stueck != berechnet.ergebnis.endpreis_je_stueck
    finally:
        db.close()


def test_legacy_snapshot_ohne_vor_faellt_auf_live_zurueck():
    """Alte Zuordnungen ohne Vor-Snapshot dürfen nicht Legacy-Additiv werden."""
    db = _session_with_schema()
    try:
        seed_top_level_markup_rates(db)
        _add_kaschieren(db)
        kasch = _kasch_live()

        obj = SpritzgussKalkulation(
            id=1,
            teilebezeichnung="Armlehne",
            teilenummer="ARM-LEGACY",
            schussgewicht_g=200.0,
            teilegewicht_netto_g=200.0,
            materialpreis_pro_kg=8.0,
            ausschussquote_pct=2.5,
            mgk_pct=3.0,
            material_nominierung="selbstnominiert",
            zykluszeit_s=40.0,
            maschinenstundensatz=80.0,
            kavitaeten=1,
            lohnstundensatz=40.0,
            fgk_pct=22.0,
            werkzeugkosten_eur=0,
            werkzeug_abrechnungsart="einmalzahlung",
            vvgk_pct=10.0,
            gewinn_pct=15.0,
            skonto_pct=0.0,
        )
        db.add(obj)
        db.flush()
        db.add(
            SpritzgussVeredelungZuordnung(
                kalkulation_id=obj.id,
                veredelungsschritt_id=1,
                reihenfolge=1,
                aktiv=True,
                mengenfaktor=1.0,
                snapshot_bezeichnung="Kaschieren TPO",
                snapshot_veredelungsart="Kaschieren",
                snapshot_kosten_inkl_ausschuss=kasch.kosten_inkl_ausschuss,
                snapshot_kosten_vor_ausschuss=None,
                snapshot_ausschussquote_pct=None,
            )
        )
        db.commit()

        zuordnungen = [
            VeredelungZuordnungInput(
                veredelungsschritt_id=1, reihenfolge=1, aktiv=True, mengenfaktor=1.0
            )
        ]
        live = spritzguss_api._build_calc_response(
            db, SpritzgussInput(**ARMLEHNE_SG), zuordnungen, use_snapshots=False
        )
        via_snap = spritzguss_api._build_calc_response(
            db,
            SpritzgussInput(**ARMLEHNE_SG),
            zuordnungen,
            use_snapshots=True,
            kalkulation_id=obj.id,
        )
        assert via_snap.ergebnis.endpreis_je_stueck == pytest.approx(
            live.ergebnis.endpreis_je_stueck
        )
    finally:
        db.close()

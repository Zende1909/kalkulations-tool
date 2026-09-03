"""Regression: FGK genau einmal – ungerundete Sollwerte und Speichern/Laden."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import spritzguss as spritzguss_api
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.scripts.seed_top_level_markup_rates import seed_top_level_markup_rates
from app.services.spritzguss_gesamt_kalkulation import berechne_gesamt
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss


def _money(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# Referenzfall ohne Veredelung, mit Setup – alle Cent-Werte nach Engine-Rundung
CASE = dict(
    schussgewicht_g=100.0,
    teilegewicht_netto_g=100.0,
    materialpreis_pro_kg=10.0,
    ausschussquote_pct=1.5,
    mgk_pct=3.0,
    material_nominierung="selbstnominiert",
    zykluszeit_s=36.0,
    maschinenstundensatz=100.0,
    kavitaeten=1,
    lohnstundensatz=50.0,
    fgk_pct=22.0,
    werkzeugkosten_eur=0,
    werkzeug_abrechnungsart="einmalzahlung",
    amortisationsvolumen=None,
    vvgk_pct=10.0,
    gewinn_pct=15.0,
    skonto_pct=0.0,
    setup_aktiv=True,
    setup_zeit_min=60.0,
    setup_maschinenstundensatz=100.0,
    setup_lohnstundensatz=50.0,
    setup_mitarbeiter=1.0,
    losgroesse=100,
)

# Sollwerte (Cent-Rundung wie Backend _money) – Fertigung über Nettokapazität
EXPECTED = dict(
    materialkosten_gesamt=1.05,  # 1.00/0.985 → 1.02; + MGK 3% → 1.05
    bruttokapazitaet=100.0,
    nettokapazitaet=98.5,
    maschinenkosten=1.02,  # 100 / 98.5
    fertigungslohn=0.51,  # 50 / 98.5
    setup_maschinenkosten_je_teil=1.00,
    setup_lohnkosten_je_teil=0.50,
    setup_kosten_je_teil=1.50,
    fgk_basis=3.03,  # 1.02 + 0.51 + 1.50
    fertigungsgemeinkosten=0.67,  # 3.03 × 0.22
    spritzguss_herstellkosten=4.75,
    gesamte_herstellkosten=4.75,
    vvgk=0.48,  # 4.75 × 0.10
    selbstkosten=5.23,
    gewinn=0.78,  # 5.23 × 0.15
    nettoverkaufspreis=6.01,
    endpreis_je_stueck=6.01,
)


def test_fgk_exact_once_unrounded_targets():
    sg = berechne_spritzguss(SpritzgussInput(**CASE))
    gesamt = berechne_gesamt(
        sg.to_dict(),
        [],
        fgk_pct=22.0,
        vvgk_pct=10.0,
        gewinn_pct=15.0,
        skonto_pct=0.0,
    )

    assert sg.materialkosten_gesamt == pytest.approx(EXPECTED["materialkosten_gesamt"])
    assert sg.bruttokapazitaet == pytest.approx(EXPECTED["bruttokapazitaet"])
    assert sg.nettokapazitaet == pytest.approx(EXPECTED["nettokapazitaet"])
    assert sg.maschinenkosten == pytest.approx(EXPECTED["maschinenkosten"])
    assert sg.fertigungslohn == pytest.approx(EXPECTED["fertigungslohn"])
    assert sg.setup_maschinenkosten_je_teil == pytest.approx(
        EXPECTED["setup_maschinenkosten_je_teil"]
    )
    assert sg.setup_lohnkosten_je_teil == pytest.approx(EXPECTED["setup_lohnkosten_je_teil"])
    assert sg.setup_kosten_je_teil == pytest.approx(EXPECTED["setup_kosten_je_teil"])

    assert gesamt.fgk_basis == pytest.approx(EXPECTED["fgk_basis"])
    assert gesamt.fertigungsgemeinkosten == pytest.approx(EXPECTED["fertigungsgemeinkosten"])
    # FGK genau einmal: Basis × 22 %, nicht verdoppelt
    assert gesamt.fertigungsgemeinkosten == pytest.approx(_money(gesamt.fgk_basis * 0.22))
    assert gesamt.fertigungsgemeinkosten == pytest.approx(sg.fertigungsgemeinkosten)

    assert gesamt.spritzguss_herstellkosten == pytest.approx(
        EXPECTED["spritzguss_herstellkosten"]
    )
    assert gesamt.gesamte_herstellkosten == pytest.approx(EXPECTED["gesamte_herstellkosten"])
    assert gesamt.spritzguss_herstellkosten == pytest.approx(gesamt.gesamte_herstellkosten)
    assert gesamt.gesamte_herstellkosten == pytest.approx(sg.herstellkosten)

    # HK = Material + Maschine + Lohn + Setup + FGK (einmal)
    assert gesamt.gesamte_herstellkosten == pytest.approx(
        _money(
            sg.materialkosten_gesamt
            + sg.maschinenkosten
            + sg.fertigungslohn
            + sg.setup_kosten_je_teil
            + gesamt.fertigungsgemeinkosten
        )
    )
    # Falsche UI-Addition Spritzguss-HK + FGK wäre zu hoch
    wrong = _money(gesamt.spritzguss_herstellkosten + gesamt.fertigungsgemeinkosten)
    assert wrong > gesamt.gesamte_herstellkosten

    assert gesamt.vvgk == pytest.approx(EXPECTED["vvgk"])
    assert gesamt.selbstkosten == pytest.approx(EXPECTED["selbstkosten"])
    assert gesamt.gewinn == pytest.approx(EXPECTED["gewinn"])
    assert gesamt.nettoverkaufspreis == pytest.approx(EXPECTED["nettoverkaufspreis"])
    assert gesamt.endpreis_je_stueck == pytest.approx(EXPECTED["endpreis_je_stueck"])

    overview = gesamt.as_ergebnisuebersicht()
    assert overview["fertigungsgemeinkosten"] == pytest.approx(EXPECTED["fertigungsgemeinkosten"])
    assert overview["gesamte_herstellkosten"] == pytest.approx(EXPECTED["gesamte_herstellkosten"])
    # Ohne Veredelung: Spritzguss-HK nicht separat (wäre Doppelanzeige des gleichen Werts)
    assert "spritzguss_herstellkosten" not in overview
    assert overview["materialkosten_gesamt"] == pytest.approx(1.05)
    assert overview["setup_kosten_je_teil"] == pytest.approx(1.50)
    assert overview["nettokapazitaet"] == pytest.approx(98.5)

def test_fgk_basis_formula_maschine_lohn_setup():
    sg = berechne_spritzguss(SpritzgussInput(**CASE))
    gesamt = berechne_gesamt(sg.to_dict(), [], fgk_pct=22.0, vvgk_pct=10.0, gewinn_pct=15.0)
    assert gesamt.fgk_basis == pytest.approx(
        _money(sg.maschinenkosten + sg.fertigungslohn + sg.setup_kosten_je_teil)
    )
    assert gesamt.setup_kosten_je_teil == pytest.approx(sg.setup_kosten_je_teil)


def _session() -> Session:
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
                    zykluszeit_quelle VARCHAR(16),
                    zykluszeit_wandstaerke_mm FLOAT,
                    zykluszeit_groessenklasse VARCHAR(16),
                    zykluszeit_prozessaufwand VARCHAR(16),
                    zykluszeit_entnahmeart VARCHAR(16),
                    zykluszeit_kuehlzeit_s FLOAT,
                    zykluszeit_nebenzeiten_gesamt_s FLOAT,
                    zykluszeit_vorschlag_s FLOAT,
                    zykluszeit_hinweis VARCHAR(512),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ,
                    teilbild_mime VARCHAR(64),
                    teilbild_data TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE spritzguss_veredelung_zuordnungen (
                    id INTEGER PRIMARY KEY,
                    kalkulation_id INTEGER NOT NULL,
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
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_fgk_berechnen_speichern_reload_identisch():
    db = _session()
    try:
        seed_top_level_markup_rates(db)
        calc_input = SpritzgussInput(**CASE)

        berechnet = spritzguss_api._build_calc_response(
            db, calc_input, [], use_snapshots=False
        )
        assert berechnet.ergebnis.endpreis_je_stueck == pytest.approx(
            EXPECTED["endpreis_je_stueck"]
        )
        assert berechnet.ergebnis.fertigungsgemeinkosten == pytest.approx(
            EXPECTED["fertigungsgemeinkosten"]
        )
        assert berechnet.ergebnis.herstellkosten == pytest.approx(
            EXPECTED["gesamte_herstellkosten"]
        )
        assert berechnet.ergebnis.vvgk == pytest.approx(EXPECTED["vvgk"])
        assert berechnet.ergebnis.gewinn == pytest.approx(EXPECTED["gewinn"])
        assert berechnet.ergebnis.verkaufspreis == pytest.approx(
            EXPECTED["endpreis_je_stueck"]
        )

        # Gemeinkosten-Block ohne zweite FGK-Zeile; Fertigung trägt FGK einmal
        assert "fertigungsgemeinkosten" not in (berechnet.bloecke.get("gemeinkosten") or {})
        assert berechnet.bloecke["fertigung"]["fertigungsgemeinkosten"] == pytest.approx(
            EXPECTED["fertigungsgemeinkosten"]
        )
        z = berechnet.bloecke.get("zusammenfassung") or {}
        assert z["fertigungsgemeinkosten"] == pytest.approx(EXPECTED["fertigungsgemeinkosten"])
        assert z["gesamte_herstellkosten"] == pytest.approx(EXPECTED["gesamte_herstellkosten"])
        assert "spritzguss_herstellkosten" not in z

        obj = SpritzgussKalkulation(
            teilebezeichnung="FGK-Check",
            teilenummer="FGK-1",
            schussgewicht_g=CASE["schussgewicht_g"],
            teilegewicht_netto_g=CASE["teilegewicht_netto_g"],
            materialpreis_pro_kg=CASE["materialpreis_pro_kg"],
            ausschussquote_pct=CASE["ausschussquote_pct"],
            mgk_pct=CASE["mgk_pct"],
            material_nominierung=CASE["material_nominierung"],
            zykluszeit_s=CASE["zykluszeit_s"],
            maschinenstundensatz=CASE["maschinenstundensatz"],
            kavitaeten=CASE["kavitaeten"],
            lohnstundensatz=CASE["lohnstundensatz"],
            fgk_pct=CASE["fgk_pct"],
            werkzeugkosten_eur=0,
            werkzeug_abrechnungsart="einmalzahlung",
            amortisationsvolumen=None,
            vvgk_pct=CASE["vvgk_pct"],
            gewinn_pct=CASE["gewinn_pct"],
            skonto_pct=CASE["skonto_pct"],
            losgroesse=CASE["losgroesse"],
            ergebnis={
                "setup_zeit_min": CASE["setup_zeit_min"],
                "setup_maschinenstundensatz": CASE["setup_maschinenstundensatz"],
                "setup_lohnstundensatz": CASE["setup_lohnstundensatz"],
                "setup_mitarbeiter": CASE["setup_mitarbeiter"],
                "setup_aktiv": CASE["setup_aktiv"],
            },
        )
        db.add(obj)
        db.flush()
        gespeichert = spritzguss_api._apply_calculation(db, obj, [], use_snapshots=True)
        db.commit()
        db.refresh(obj)

        keys = (
            "fertigungsgemeinkosten",
            "fgk_basis",
            "herstellkosten",
            "vvgk",
            "gewinn",
            "endpreis_je_stueck",
            "verkaufspreis",
        )
        for key in keys:
            assert getattr(gespeichert.ergebnis, key) == pytest.approx(
                getattr(berechnet.ergebnis, key)
            ), key
            stored = obj.ergebnis[key] if isinstance(obj.ergebnis, dict) else None
            assert stored == pytest.approx(getattr(berechnet.ergebnis, key)), f"stored.{key}"

        geladen = spritzguss_api._kalkulation_to_read(db, obj)
        assert geladen.ergebnis["endpreis_je_stueck"] == pytest.approx(
            berechnet.ergebnis.endpreis_je_stueck
        )
        assert geladen.ergebnis["fertigungsgemeinkosten"] == pytest.approx(
            EXPECTED["fertigungsgemeinkosten"]
        )
        assert geladen.ergebnis["herstellkosten"] == pytest.approx(
            EXPECTED["gesamte_herstellkosten"]
        )

        reload = spritzguss_api._build_calc_response(
            db,
            spritzguss_api._to_calc_input_from_model(obj),
            [],
            use_snapshots=False,
        )
        for key in keys:
            assert getattr(reload.ergebnis, key) == pytest.approx(
                getattr(berechnet.ergebnis, key)
            ), f"reload.{key}"
    finally:
        db.close()

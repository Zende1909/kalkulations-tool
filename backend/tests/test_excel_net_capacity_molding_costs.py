"""Regression: Excel-Materialpfad – MGK genau einmal, Engine == API.

Excel-Materialzeilen (Beispielkalkulation)::

    direkte Materialkosten     21,00
    Materialausschuss (1 %)     0,21
    MGK-Basis                  21,21
    Material-MGK 3 % (ungerundet 0,6363)
    Material gesamt            21,85 (Cent) / 21,8463 ungerundet

Ursache der früheren API-Abweichung (~34,37 statt 33,53):
Ein Test-/Vergleichspfad nutzte Schussgewicht 2163 g mit ``mgk_pct=0``, sodass
``materialkosten_gesamt`` bereits 21,85 betrug; die API setzte danach den
zentralen MGK-Satz 3 % erneut auf die echten Materialkosten inkl. Ausschuss.
Korrekt: direkte Kosten 21,00 (2100 g × 10 €/kg), MGK genau einmal.
"""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1 import spritzguss as spritzguss_api
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.scripts.seed_top_level_markup_rates import seed_top_level_markup_rates
from app.services.export_builders import _float_from
from app.services.spritzguss_gesamt_kalkulation import (
    VeredelungSchrittEingabe,
    berechne_gesamt,
)
from app.services.spritzguss_kalkulation import (
    SpritzgussInput,
    berechne_spritzguss,
    excel_round_0,
)
from app.services.veredelung_kalkulation import VeredelungInput, berechne_veredelung


def _money(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


# Excel: 2100 g × 10 €/kg = 21,00 direkt; MGK 3 % einmal
EXCEL_CASE = dict(
    teilegewicht_netto_g=996.0,
    schussgewicht_g=2100.0,
    materialpreis_pro_kg=10.0,
    ausschussquote_pct=1.0,
    mgk_pct=3.0,
    material_nominierung="selbstnominiert",
    zykluszeit_s=500.0,
    maschinenstundensatz=40.610485,
    kavitaeten=2,
    lohnstundensatz=12.0,
    fgk_pct=22.0,
    werkzeugkosten_eur=0,
    werkzeug_abrechnungsart="einmalzahlung",
    amortisationsvolumen=None,
    vvgk_pct=10.0,
    gewinn_pct=15.0,
    skonto_pct=0.0,
    setup_aktiv=True,
    setup_zeit_min=80.0,
    setup_maschinenstundensatz=40.610485,
    setup_lohnstundensatz=25.0,
    setup_mitarbeiter=1.5,
    losgroesse=4808,
)

EXPECTED = dict(
    materialkosten=21.00,
    materialausschuss_betrag=0.21,
    mgk_basis=21.21,
    material_mgk_unrounded=0.6363,
    material_gesamt_unrounded=21.8463,
    materialgemeinkosten=0.64,
    materialkosten_gesamt=21.85,
    bruttokapazitaet_exakt=14.4,
    bruttokapazitaet=14.0,
    nettokapazitaet=13.86,
    maschinenkosten=2.93,
    fertigungslohn=0.87,
    setup_kosten_je_teil=0.02,
    fgk_basis=3.82,
    fertigungsgemeinkosten=0.84,
    herstellkosten=26.51,
    vvgk=2.65,
    selbstkosten=29.16,
    gewinn=4.37,
    endpreis=33.53,
)


def test_excel_round_0_matches_excel():
    assert excel_round_0(Decimal("14.4")) == Decimal("14")
    assert excel_round_0(Decimal("14.5")) == Decimal("15")


def test_excel_material_mgk_once_unrounded():
    sg = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    assert sg.materialkosten == pytest.approx(EXPECTED["materialkosten"])
    assert sg.materialausschuss_betrag == pytest.approx(EXPECTED["materialausschuss_betrag"])
    assert sg.materialkosten_inkl_ausschuss == pytest.approx(EXPECTED["mgk_basis"])
    assert sg.mgk_basis == pytest.approx(EXPECTED["mgk_basis"])
    assert sg.applied_mgk_pct == pytest.approx(3.0)

    mgk_raw = sg.mgk_basis * (sg.applied_mgk_pct / 100.0)
    assert mgk_raw == pytest.approx(EXPECTED["material_mgk_unrounded"], abs=1e-6)
    assert sg.mgk_basis + mgk_raw == pytest.approx(
        EXPECTED["material_gesamt_unrounded"], abs=1e-6
    )
    assert sg.materialgemeinkosten == pytest.approx(EXPECTED["materialgemeinkosten"])
    assert sg.materialkosten_gesamt == pytest.approx(EXPECTED["materialkosten_gesamt"])

    # Keine Doppel-MGK: nicht nochmals 3 % auf materialkosten_gesamt
    doppel = _money(sg.materialkosten_gesamt * 1.03)
    assert doppel == pytest.approx(22.51)
    assert sg.materialkosten_gesamt != pytest.approx(doppel)
    assert sg.fgk_basis == pytest.approx(
        _money(sg.maschinenkosten + sg.fertigungslohn + sg.setup_kosten_je_teil)
    )
    # FGK-Basis enthält weder Material noch Material-MGK
    assert sg.fgk_basis == pytest.approx(EXPECTED["fgk_basis"], abs=0.01)
    assert abs(sg.fgk_basis - sg.materialkosten_gesamt) > 1.0


def test_excel_900t_full_stack_endpreis():
    sg = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    assert sg.bruttokapazitaet_exakt == pytest.approx(EXPECTED["bruttokapazitaet_exakt"])
    assert sg.bruttokapazitaet == pytest.approx(EXPECTED["bruttokapazitaet"])
    assert sg.nettokapazitaet == pytest.approx(EXPECTED["nettokapazitaet"])
    assert sg.maschinenkosten == pytest.approx(EXPECTED["maschinenkosten"], abs=0.01)
    assert sg.fertigungslohn == pytest.approx(EXPECTED["fertigungslohn"], abs=0.01)
    assert sg.setup_kosten_je_teil == pytest.approx(EXPECTED["setup_kosten_je_teil"], abs=0.01)
    assert sg.fgk_basis == pytest.approx(EXPECTED["fgk_basis"], abs=0.01)
    assert sg.fertigungsgemeinkosten == pytest.approx(
        EXPECTED["fertigungsgemeinkosten"], abs=0.01
    )
    assert sg.herstellkosten == pytest.approx(EXPECTED["herstellkosten"], abs=0.01)
    assert sg.vvgk == pytest.approx(EXPECTED["vvgk"], abs=0.01)
    assert sg.gewinn == pytest.approx(EXPECTED["gewinn"], abs=0.01)
    assert sg.verkaufspreis == pytest.approx(EXPECTED["endpreis"], abs=0.01)

    gesamt = berechne_gesamt(
        sg.to_dict(), [], fgk_pct=22.0, vvgk_pct=10.0, gewinn_pct=15.0, skonto_pct=0.0
    )
    assert gesamt.gesamte_herstellkosten == pytest.approx(sg.herstellkosten)
    assert gesamt.fertigungsgemeinkosten == pytest.approx(sg.fertigungsgemeinkosten)
    assert gesamt.endpreis_je_stueck == pytest.approx(EXPECTED["endpreis"], abs=0.01)


def test_kein_ausschuss_kapazitaet_equals_brutto():
    sg = berechne_spritzguss(
        SpritzgussInput(**{**EXCEL_CASE, "ausschussquote_pct": 0.0})
    )
    assert sg.bruttokapazitaet == 14.0
    assert sg.nettokapazitaet == 14.0
    assert sg.materialausschuss_betrag == 0.0
    assert sg.maschinenkosten == pytest.approx(_money(40.610485 / 14.0))


def test_ausschuss_gt_zero_raises_direct_costs():
    ohne = berechne_spritzguss(
        SpritzgussInput(**{**EXCEL_CASE, "ausschussquote_pct": 0.0})
    )
    mit = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    assert mit.maschinenkosten > ohne.maschinenkosten
    assert mit.fertigungslohn > ohne.fertigungslohn


def test_unterschiedliche_kavitaeten_aendern_brutto():
    k1 = berechne_spritzguss(SpritzgussInput(**{**EXCEL_CASE, "kavitaeten": 1}))
    k2 = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    assert k1.bruttokapazitaet == 7.0
    assert k2.bruttokapazitaet == 14.0
    assert k1.maschinenkosten > k2.maschinenkosten


def test_setup_aktiv_vs_deaktiviert():
    mit = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    ohne = berechne_spritzguss(
        SpritzgussInput(
            **{
                **EXCEL_CASE,
                "setup_aktiv": False,
                "setup_zeit_min": 0,
                "losgroesse": None,
            }
        )
    )
    assert mit.setup_kosten_je_teil > 0
    assert ohne.setup_kosten_je_teil == 0
    setup_raw = (80 / 60) * (40.610485 + 25.0 * 1.5) / 4808
    assert mit.setup_kosten_je_teil == pytest.approx(setup_raw)


def test_mit_und_ohne_veredelung_fgk_einmal():
    sg = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    ohne = berechne_gesamt(sg.to_dict(), [], fgk_pct=22, vvgk_pct=10, gewinn_pct=15)
    verd = berechne_veredelung(
        VeredelungInput(
            taktzeit_s=36.0,
            anzahl_mitarbeiter=1,
            lohnstundensatz=50.0,
            maschinenstundensatz=100.0,
            verbrauchskosten_je_stueck=0.5,
            ausschussquote_pct=0.0,
            fgk_pct=0,
            reihenfolge=1,
        )
    )
    mit = berechne_gesamt(
        sg.to_dict(),
        [
            VeredelungSchrittEingabe(
                veredelungsschritt_id=1,
                bezeichnung="Montage",
                veredelungsart="Montage",
                reihenfolge=1,
                aktiv=True,
                mengenfaktor=1.0,
                kosten_inkl_ausschuss=verd.kosten_inkl_ausschuss,
                kosten_vor_ausschuss=verd.kosten_vor_ausschuss,
                ausschussquote_pct=0.0,
            )
        ],
        fgk_pct=22,
        vvgk_pct=10,
        gewinn_pct=15,
    )
    assert mit.fertigungsgemeinkosten == pytest.approx(_money(mit.fgk_basis * 0.22))
    assert mit.gesamte_herstellkosten > ohne.gesamte_herstellkosten


def test_wrong_baseline_2163_with_zero_mgk_then_central_diverges():
    """Dokumentiert die frühere Fehlannahme: 21,85 schon „fertig“, dann + MGK."""
    fake = berechne_spritzguss(
        SpritzgussInput(**{**EXCEL_CASE, "schussgewicht_g": 2163.0, "mgk_pct": 0.0})
    )
    assert fake.materialkosten_gesamt == pytest.approx(21.85)
    inflated = berechne_spritzguss(
        SpritzgussInput(**{**EXCEL_CASE, "schussgewicht_g": 2163.0, "mgk_pct": 3.0})
    )
    assert inflated.materialkosten_gesamt == pytest.approx(22.51)
    assert inflated.verkaufspreis == pytest.approx(34.37, abs=0.01)
    correct = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    assert correct.verkaufspreis == pytest.approx(33.53, abs=0.01)
    assert inflated.verkaufspreis != pytest.approx(correct.verkaufspreis)


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
                    customer_id INTEGER, program_id INTEGER, project_id INTEGER,
                    calculation_year INTEGER, project_volume FLOAT, werk_id INTEGER,
                    losgroesse INTEGER, losgroesse_modus VARCHAR(16), losgroesse_manuell INTEGER, material_id INTEGER,
                    schussgewicht_g FLOAT NOT NULL DEFAULT 0,
                    teilegewicht_netto_g FLOAT NOT NULL DEFAULT 0,
                    ausschussquote_pct FLOAT NOT NULL DEFAULT 0,
                    materialpreis_pro_kg FLOAT NOT NULL DEFAULT 0,
                    material_nominierung VARCHAR(32),
                    maschine_id INTEGER, zykluszeit_s FLOAT NOT NULL DEFAULT 0,
                    kavitaeten INTEGER NOT NULL DEFAULT 1,
                    maschinenstundensatz FLOAT NOT NULL DEFAULT 0,
                    lohnkosten_id INTEGER, lohnstundensatz FLOAT NOT NULL DEFAULT 0,
                    werkzeug_abrechnungsart VARCHAR(32) NOT NULL DEFAULT 'einmalzahlung',
                    werkzeugkosten_eur FLOAT NOT NULL DEFAULT 0,
                    amortisationsvolumen INTEGER,
                    mgk_pct FLOAT NOT NULL DEFAULT 0, fgk_pct FLOAT NOT NULL DEFAULT 0,
                    vvgk_pct FLOAT NOT NULL DEFAULT 0, gewinn_pct FLOAT NOT NULL DEFAULT 0,
                    skonto_pct FLOAT NOT NULL DEFAULT 0,
                    ergebnis TEXT, ergebnis_bloecke TEXT,
                    notizen TEXT NOT NULL DEFAULT '', aktiv BOOLEAN NOT NULL DEFAULT 1,
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


def test_api_central_mgk_matches_engine_endpreis_33_53():
    """API mit Stammdaten-MGK 3 % == Engine mit mgk_pct=3; Endpreis 33,53."""
    db = _session()
    try:
        seed_top_level_markup_rates(db)
        # Client liefert mgk_pct=0 – zentrale Sätze setzen 3 %
        client_input = SpritzgussInput(**{**EXCEL_CASE, "mgk_pct": 0.0, "fgk_pct": 0.0,
                                          "vvgk_pct": 0.0, "gewinn_pct": 0.0, "skonto_pct": 0.0})
        engine_only = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
        api_resp = spritzguss_api._build_calc_response(
            db, client_input, [], use_snapshots=False
        )
        assert api_resp.ergebnis.applied_mgk_pct == pytest.approx(3.0)
        assert api_resp.ergebnis.materialkosten == pytest.approx(21.00)
        assert api_resp.ergebnis.mgk_basis == pytest.approx(21.21)
        assert api_resp.ergebnis.materialgemeinkosten == pytest.approx(0.64)
        assert api_resp.ergebnis.materialkosten_gesamt == pytest.approx(21.85)
        assert api_resp.ergebnis.verkaufspreis == pytest.approx(33.53, abs=0.01)
        assert api_resp.ergebnis.verkaufspreis == pytest.approx(engine_only.verkaufspreis)
        assert api_resp.ergebnis.materialkosten_gesamt == pytest.approx(
            engine_only.materialkosten_gesamt
        )
        # FGK ohne Material/MGK
        assert api_resp.ergebnis.fgk_basis == pytest.approx(3.82, abs=0.01)
    finally:
        db.close()


def test_excel_case_berechnen_speichern_reload_export_parity():
    db = _session()
    try:
        seed_top_level_markup_rates(db)
        calc_input = SpritzgussInput(**{**EXCEL_CASE, "mgk_pct": 0.0})
        berechnet = spritzguss_api._build_calc_response(
            db, calc_input, [], use_snapshots=False
        )
        assert berechnet.ergebnis.verkaufspreis == pytest.approx(33.53, abs=0.01)
        assert berechnet.ergebnis.materialkosten_gesamt == pytest.approx(21.85)
        assert berechnet.ergebnis.materialausschuss_betrag == pytest.approx(0.21)

        obj = SpritzgussKalkulation(
            teilebezeichnung="Excel-900t",
            teilenummer="EX-900",
            schussgewicht_g=EXCEL_CASE["schussgewicht_g"],
            teilegewicht_netto_g=EXCEL_CASE["teilegewicht_netto_g"],
            materialpreis_pro_kg=EXCEL_CASE["materialpreis_pro_kg"],
            ausschussquote_pct=EXCEL_CASE["ausschussquote_pct"],
            mgk_pct=0.0,
            material_nominierung=EXCEL_CASE["material_nominierung"],
            zykluszeit_s=EXCEL_CASE["zykluszeit_s"],
            maschinenstundensatz=EXCEL_CASE["maschinenstundensatz"],
            kavitaeten=EXCEL_CASE["kavitaeten"],
            lohnstundensatz=EXCEL_CASE["lohnstundensatz"],
            fgk_pct=0.0,
            vvgk_pct=0.0,
            gewinn_pct=0.0,
            skonto_pct=0.0,
            werkzeugkosten_eur=0,
            werkzeug_abrechnungsart="einmalzahlung",
            losgroesse=4808,
            ergebnis={
                "setup_zeit_min": 80.0,
                "setup_maschinenstundensatz": 40.610485,
                "setup_lohnstundensatz": 25.0,
                "setup_mitarbeiter": 1.5,
                "setup_aktiv": True,
            },
        )
        db.add(obj)
        db.flush()
        gespeichert = spritzguss_api._apply_calculation(db, obj, [], use_snapshots=True)
        db.commit()
        db.refresh(obj)

        keys = (
            "materialkosten",
            "materialkosten_inkl_ausschuss",
            "materialausschuss_betrag",
            "mgk_basis",
            "materialgemeinkosten",
            "materialkosten_gesamt",
            "maschinenkosten",
            "fertigungslohn",
            "fertigungsgemeinkosten",
            "herstellkosten",
            "vvgk",
            "gewinn",
            "verkaufspreis",
            "nettokapazitaet",
            "applied_mgk_pct",
        )
        for key in keys:
            assert getattr(gespeichert.ergebnis, key) == pytest.approx(
                getattr(berechnet.ergebnis, key)
            ), key
            assert obj.ergebnis[key] == pytest.approx(getattr(berechnet.ergebnis, key)), key

        reload = spritzguss_api._build_calc_response(
            db, spritzguss_api._to_calc_input_from_model(obj), [], use_snapshots=False
        )
        assert reload.ergebnis.verkaufspreis == pytest.approx(33.53, abs=0.01)
        assert reload.ergebnis.materialgemeinkosten == pytest.approx(0.64)
        assert reload.ergebnis.applied_mgk_pct == pytest.approx(3.0)

        # Export-Keys aus gespeichertem Ergebnis
        erg = obj.ergebnis
        assert _float_from(erg, "materialkosten") == pytest.approx(21.00)
        assert _float_from(erg, "materialausschuss_betrag") == pytest.approx(0.21)
        assert _float_from(erg, "mgk_basis") == pytest.approx(21.21)
        assert _float_from(erg, "materialgemeinkosten") == pytest.approx(0.64)
        assert _float_from(erg, "materialkosten_gesamt") == pytest.approx(21.85)
        assert _float_from(erg, "verkaufspreis") == pytest.approx(33.53, abs=0.01)
    finally:
        db.close()

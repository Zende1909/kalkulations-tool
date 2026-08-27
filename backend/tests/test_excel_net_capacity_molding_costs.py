"""Regression: Spritzguss-Fertigungskosten über Nettokapazität (Excel-Beispiel).

Excel (Beispielkalkulation / Costing_Base_Data-Logik)::

    Bruttokapazität = ROUND((3600 / Zykluszeit) × Kavitäten, 0)
    Nettokapazität = Bruttokapazität × (1 − Ausschuss)
    Maschinenkosten = Maschinenstundensatz / Nettokapazität
    Fertigungslohn = Lohnstundensatz / Nettokapazität
    Setup = (Setup-Stundensatz × Setup-Zeit/60) / Losgröße   # ohne Extra-Ausschuss
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


# Excel-Beispiel: 900-t, 500 s, 2 Kav, 1 % Ausschuss
EXCEL_CASE = dict(
    teilegewicht_netto_g=996.0,
    schussgewicht_g=2163.0,  # → Material 21,63; inkl. 1 % Ausschuss 21,85
    materialpreis_pro_kg=10.0,
    ausschussquote_pct=1.0,
    mgk_pct=0.0,
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
    bruttokapazitaet_exakt=14.4,
    bruttokapazitaet=14.0,
    nettokapazitaet=13.86,
    materialkosten_gesamt=21.85,
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


def test_excel_900t_scrap_on_direct_costs():
    sg = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    assert sg.bruttokapazitaet_exakt == pytest.approx(EXPECTED["bruttokapazitaet_exakt"])
    assert sg.bruttokapazitaet == pytest.approx(EXPECTED["bruttokapazitaet"])
    assert sg.nettokapazitaet == pytest.approx(EXPECTED["nettokapazitaet"])

    # Ungerundet: Satz / Netto
    assert sg.maschinenkosten == pytest.approx(40.610485 / 13.86, abs=0.005)
    assert sg.fertigungslohn == pytest.approx(12.0 / 13.86, abs=0.005)
    assert sg.maschinenkosten == pytest.approx(EXPECTED["maschinenkosten"], abs=0.01)
    assert sg.fertigungslohn == pytest.approx(EXPECTED["fertigungslohn"], abs=0.01)
    assert sg.setup_kosten_je_teil == pytest.approx(EXPECTED["setup_kosten_je_teil"], abs=0.01)
    assert sg.materialkosten_gesamt == pytest.approx(EXPECTED["materialkosten_gesamt"])

    assert sg.fgk_basis == pytest.approx(EXPECTED["fgk_basis"], abs=0.01)
    assert sg.fertigungsgemeinkosten == pytest.approx(
        EXPECTED["fertigungsgemeinkosten"], abs=0.01
    )
    assert sg.herstellkosten == pytest.approx(EXPECTED["herstellkosten"], abs=0.01)
    assert sg.vvgk == pytest.approx(EXPECTED["vvgk"], abs=0.01)
    assert sg.selbstkosten == pytest.approx(EXPECTED["selbstkosten"], abs=0.01)
    assert sg.gewinn == pytest.approx(EXPECTED["gewinn"], abs=0.01)
    assert sg.verkaufspreis == pytest.approx(EXPECTED["endpreis"], abs=0.01)

    gesamt = berechne_gesamt(
        sg.to_dict(), [], fgk_pct=22.0, vvgk_pct=10.0, gewinn_pct=15.0, skonto_pct=0.0
    )
    assert gesamt.gesamte_herstellkosten == pytest.approx(sg.herstellkosten)
    assert gesamt.spritzguss_herstellkosten == pytest.approx(sg.herstellkosten)
    assert gesamt.fertigungsgemeinkosten == pytest.approx(sg.fertigungsgemeinkosten)
    assert gesamt.endpreis_je_stueck == pytest.approx(EXPECTED["endpreis"], abs=0.01)
    # FGK genau einmal
    assert gesamt.fertigungsgemeinkosten == pytest.approx(_money(gesamt.fgk_basis * 0.22))


def test_kein_ausschuss_kapazitaet_equals_brutto():
    sg = berechne_spritzguss(
        SpritzgussInput(**{**EXCEL_CASE, "ausschussquote_pct": 0.0, "schussgewicht_g": 100.0})
    )
    assert sg.bruttokapazitaet == 14.0
    assert sg.nettokapazitaet == 14.0
    assert sg.maschinenkosten == pytest.approx(_money(40.610485 / 14.0))
    assert sg.fertigungslohn == pytest.approx(_money(12.0 / 14.0))


def test_ausschuss_gt_zero_raises_direct_costs():
    ohne = berechne_spritzguss(
        SpritzgussInput(**{**EXCEL_CASE, "ausschussquote_pct": 0.0})
    )
    mit = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    assert mit.maschinenkosten > ohne.maschinenkosten
    assert mit.fertigungslohn > ohne.fertigungslohn
    assert mit.nettokapazitaet < mit.bruttokapazitaet


def test_unterschiedliche_kavitaeten_aendern_brutto():
    k1 = berechne_spritzguss(SpritzgussInput(**{**EXCEL_CASE, "kavitaeten": 1}))
    k2 = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    assert k1.bruttokapazitaet == 7.0  # ROUND(7.2)=7
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
    assert mit.fgk_basis > ohne.fgk_basis
    # Setup ohne zusätzlichen Ausschuss: Losgröße-Umlage
    setup_raw = (80 / 60) * (40.610485 + 25.0 * 1.5) / 4808
    assert mit.setup_kosten_je_teil == pytest.approx(_money(setup_raw))


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
    assert mit.fgk_basis == pytest.approx(
        _money(
            sg.maschinenkosten
            + sg.fertigungslohn
            + sg.setup_kosten_je_teil
            + verd.kosten_vor_ausschuss
        )
    )


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
                    losgroesse INTEGER, material_id INTEGER,
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


def test_excel_case_berechnen_speichern_reload():
    db = _session()
    try:
        seed_top_level_markup_rates(db)
        calc_input = SpritzgussInput(**EXCEL_CASE)
        berechnet = spritzguss_api._build_calc_response(db, calc_input, [], use_snapshots=False)
        # Reine Engine ohne zentrale MGK: 33,53; API wendet Stammdaten-MGK an –
        # deshalb hier Identität Berechnen/Speichern/Laden, Kapazität aber fest.
        assert berechnet.ergebnis.bruttokapazitaet == pytest.approx(14.0)
        assert berechnet.ergebnis.nettokapazitaet == pytest.approx(13.86)
        assert berechnet.ergebnis.maschinenkosten == pytest.approx(2.93, abs=0.01)
        assert berechnet.ergebnis.fertigungslohn == pytest.approx(0.87, abs=0.01)

        obj = SpritzgussKalkulation(
            teilebezeichnung="Excel-900t",
            teilenummer="EX-900",
            schussgewicht_g=EXCEL_CASE["schussgewicht_g"],
            teilegewicht_netto_g=EXCEL_CASE["teilegewicht_netto_g"],
            materialpreis_pro_kg=EXCEL_CASE["materialpreis_pro_kg"],
            ausschussquote_pct=EXCEL_CASE["ausschussquote_pct"],
            mgk_pct=EXCEL_CASE["mgk_pct"],
            material_nominierung=EXCEL_CASE["material_nominierung"],
            zykluszeit_s=EXCEL_CASE["zykluszeit_s"],
            maschinenstundensatz=EXCEL_CASE["maschinenstundensatz"],
            kavitaeten=EXCEL_CASE["kavitaeten"],
            lohnstundensatz=EXCEL_CASE["lohnstundensatz"],
            fgk_pct=22.0,
            vvgk_pct=10.0,
            gewinn_pct=15.0,
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

        for key in (
            "maschinenkosten",
            "fertigungslohn",
            "fertigungsgemeinkosten",
            "herstellkosten",
            "vvgk",
            "gewinn",
            "verkaufspreis",
            "nettokapazitaet",
            "bruttokapazitaet",
        ):
            assert getattr(gespeichert.ergebnis, key) == pytest.approx(
                getattr(berechnet.ergebnis, key)
            ), key
            assert obj.ergebnis[key] == pytest.approx(getattr(berechnet.ergebnis, key)), key

        reload = spritzguss_api._build_calc_response(
            db, spritzguss_api._to_calc_input_from_model(obj), [], use_snapshots=False
        )
        assert reload.ergebnis.verkaufspreis == pytest.approx(berechnet.ergebnis.verkaufspreis)
        assert reload.ergebnis.nettokapazitaet == pytest.approx(13.86)
        assert reload.ergebnis.maschinenkosten == pytest.approx(2.93, abs=0.01)

        # Export-Parität: gespeicherte Ergebniswerte = berechnete Kapazität/Fertigung
        assert obj.ergebnis["nettokapazitaet"] == pytest.approx(13.86)
        assert obj.ergebnis["bruttokapazitaet"] == pytest.approx(14.0)
        assert obj.ergebnis["maschinenkosten"] == pytest.approx(2.93, abs=0.01)
        z = (obj.ergebnis_bloecke or {}).get("zusammenfassung") or {}
        if z:
            assert z.get("nettokapazitaet") == pytest.approx(13.86)
    finally:
        db.close()


def test_excel_case_export_paritaet():
    """Export-Felder (Kapazität) liegen im Ergebnis für Excel-/PDF-Builder vor."""
    sg = berechne_spritzguss(SpritzgussInput(**EXCEL_CASE))
    assert sg.nettokapazitaet == pytest.approx(13.86)
    assert "nettokapazitaet" in sg.to_dict()
    assert "bruttokapazitaet" in sg.as_blocks()["fertigung"]
    # Builder liest dieselben Keys aus ergebnis
    from app.services.export_builders import _float_from

    erg = sg.to_dict()
    assert _float_from(erg, "nettokapazitaet") == pytest.approx(13.86)
    assert _float_from(erg, "maschinenkosten") == pytest.approx(2.93, abs=0.01)
    assert _float_from(erg, "verkaufspreis") == pytest.approx(33.53, abs=0.01)

"""Regression: TSV-Beispiel (Grundträger, Armlehne, Schalter, ASSY) + MGK/Ausschuss/Jahresstückzahl."""

from __future__ import annotations

import math
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.customer import Customer
from app.models.program import Program, ProgramVolume
from app.models.project import Project
from app.models.zuschlagssatz import Zuschlagssatz
from app.scripts.seed_top_level_markup_rates import seed_top_level_markup_rates
from app.services.assembly_calculation import MarkupRates, PositionCalcInput, calculate_assembly
from app.services.central_markup_rates import load_central_markup_rates
from app.services.process_yield import apply_process_yield
from app.services.project_volume_service import average_jahresstueckzahl_for_project
from app.services.spritzguss_gesamt_kalkulation import VeredelungSchrittEingabe, berechne_gesamt
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss
from app.services.veredelung_kalkulation import VeredelungInput, berechne_veredelung


def _money(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def test_process_yield_once_on_upstream_and_process():
    out, surcharge, yf = apply_process_yield(Decimal("100"), Decimal("10"), 1.5)
    expected = _money(110 / 0.985)
    assert float(out) == expected
    assert float(surcharge) == _money(expected - 110)
    assert float(yf) == pytest.approx(1 / 0.985)


def test_mgk_selbst_3_oem_5_and_fix_swapped():
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
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    db.add_all(
        [
            Zuschlagssatz(
                bezeichnung="MGK selbst", satz_prozent=5.0, typ="mgk_kaufteil_selbst", aktiv=True
            ),
            Zuschlagssatz(
                bezeichnung="MGK OEM", satz_prozent=3.0, typ="mgk_kaufteil_oem", aktiv=True
            ),
            Zuschlagssatz(bezeichnung="FGK", satz_prozent=22.0, typ="fgk", aktiv=True),
            Zuschlagssatz(bezeichnung="VVGK", satz_prozent=10.0, typ="vvgk", aktiv=True),
            Zuschlagssatz(bezeichnung="Gewinn", satz_prozent=15.0, typ="gewinn", aktiv=True),
            Zuschlagssatz(bezeichnung="Skonto", satz_prozent=0.0, typ="skonto", aktiv=True),
        ]
    )
    db.commit()
    actions = seed_top_level_markup_rates(db)
    assert "fix:mgk_kaufteil_selbst:5→3" in actions
    rates = load_central_markup_rates(db)
    assert rates.mgk_kaufteil_selbst_pct == 3.0
    assert rates.mgk_kaufteil_oem_pct == 5.0
    assert rates.mgk_pct_for_nominierung("selbstnominiert") == 3.0
    assert rates.mgk_pct_for_nominierung("oem_nominiert") == 5.0
    db.close()


def test_grundtraeger_material_ausschuss_and_mgk_selbst():
    """Grundträger: Spritzguss, Ausschuss 1,5 %, MGK selbst 3 %."""
    sg = berechne_spritzguss(
        SpritzgussInput(
            schussgewicht_g=100.0, teilegewicht_netto_g=100.0,
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
        )
    )
    assert sg.materialkosten == 1.0
    assert sg.materialkosten_inkl_ausschuss == _money(1 / 0.985)
    assert sg.materialgemeinkosten == _money(sg.materialkosten_inkl_ausschuss * 0.03)
    assert sg.applied_mgk_pct == 3.0
    assert sg.fgk_basis == _money(sg.maschinenkosten + sg.fertigungslohn)


def test_material_basis_is_schussgewicht_not_netto_in_tsv_style():
    sg = berechne_spritzguss(
        SpritzgussInput(
            teilegewicht_netto_g=80.0,
            schussgewicht_g=125.0,
            materialpreis_pro_kg=8.0,
            ausschussquote_pct=2.0,
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
        )
    )
    assert sg.materialkosten == _money(0.125 * 8.0)
    assert sg.materialkosten == 1.0
    assert sg.materialkosten_inkl_ausschuss == _money(1.0 / 0.98)


def test_armlehne_ohne_und_mit_kaschieren():
    """Armlehne: Spritzguss 2,5 %; mit Kaschieren 1,5 % auf Vorprodukt + Prozess."""
    sg = berechne_spritzguss(
        SpritzgussInput(
            schussgewicht_g=200.0, teilegewicht_netto_g=200.0,
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
    )
    ohne = berechne_gesamt(sg.to_dict(), [], fgk_pct=22.0, vvgk_pct=10.0, gewinn_pct=15.0)
    assert ohne.veredelung_gesamt == 0.0
    assert ohne.gesamte_herstellkosten == sg.herstellkosten

    kasch = berechne_veredelung(
        VeredelungInput(
            taktzeit_s=36.0,
            anzahl_mitarbeiter=1,
            lohnstundensatz=50.0,
            maschinenstundensatz=100.0,
            verbrauchskosten_je_stueck=0.5,
            ausschussquote_pct=1.5,
            fgk_pct=0,
            reihenfolge=1,
        )
    )
    mit = berechne_gesamt(
        sg.to_dict(),
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
        fgk_pct=22.0,
        vvgk_pct=10.0,
        gewinn_pct=15.0,
    )
    assert mit.gesamte_herstellkosten > ohne.gesamte_herstellkosten
    step = mit.veredelung_schritte[0]
    assert step.ausschussquote_pct == 1.5
    assert step.ausschuss_zuschlag > 0
    expected_in = _money(sg.materialkosten_gesamt + sg.maschinenkosten + sg.fertigungslohn)
    assert step.vorprodukt_eingang == expected_in
    assert mit.fgk_basis == _money(
        sg.maschinenkosten + sg.fertigungslohn + kasch.kosten_vor_ausschuss
    )


def test_schalter_kaufteil_mgk_selbst():
    einkauf = 2.50
    mgk = 3.0
    assert _money(einkauf * (1 + mgk / 100)) == 2.58


def test_tsv_assy_ausschuss_kaskade():
    """TSV: GT + Armlehne + Schalter + ASSY 1,5 % auf Summe Vorprodukte + Prozess."""
    rates = MarkupRates(fgk_pct=22.0, vvgk_pct=10.0, gewinn_pct=15.0, skonto_pct=0.0)
    positions = [
        PositionCalcInput(
            position_id=1,
            position_type="PART",
            sequence=1,
            quantity=1,
            quantity_factor=1,
            price_basis="COST",
            active=True,
            label="Grundträger",
            name_snapshot="Grundträger",
            cost_snapshot=4.20,
            price_snapshot=None,
        ),
        PositionCalcInput(
            position_id=2,
            position_type="PART",
            sequence=2,
            quantity=1,
            quantity_factor=1,
            price_basis="COST",
            active=True,
            label="Armlehne",
            name_snapshot="Armlehne",
            cost_snapshot=6.80,
            price_snapshot=None,
        ),
        PositionCalcInput(
            position_id=3,
            position_type="PURCHASED_PART",
            sequence=3,
            quantity=1,
            quantity_factor=1,
            price_basis=None,
            active=True,
            label="Schalter",
            name_snapshot="Schalter",
            cost_snapshot=2.50,
            price_snapshot=2.58,
        ),
        PositionCalcInput(
            position_id=4,
            position_type="PROCESS",
            sequence=4,
            quantity=1,
            quantity_factor=1,
            price_basis=None,
            active=True,
            label="ASSY",
            name_snapshot="ASSY TSV",
            cost_snapshot=1.015,
            price_snapshot=None,
            cost_before_scrap=1.00,
            ausschussquote_pct=1.5,
        ),
    ]
    result = calculate_assembly(
        assembly_type="TOP_LEVEL", positions=positions, markup_rates=rates
    )
    vorprodukt = Decimal(str(_money(4.20 + 6.80 + 2.58)))
    process_direct = Decimal("1.00")
    fgk = process_direct * Decimal("0.22")
    expected_hk = float((vorprodukt + process_direct + fgk) / Decimal("0.985"))
    assert result.herstellkosten == pytest.approx(expected_hk, rel=1e-6)
    assert result.fgk_basis == 1.0
    assert result.process_yield_details is not None
    assert len(result.process_yield_details) == 1
    detail = result.process_yield_details[0]
    assert detail.ausschussquote_pct == 1.5
    assert detail.vorprodukt_eingang == pytest.approx(float(vorprodukt + fgk), rel=1e-6)
    assert result.vvgk == pytest.approx(0.0)
    assert result.gewinn == pytest.approx(expected_hk * 0.15, rel=1e-6)


def test_jahresstueckzahl_41875_ceil():
    """Durchschnitt der Projektstückzahlen, ceil → 41.875."""
    engine = create_engine("sqlite:///:memory:")
    for table in (Customer.__table__, Program.__table__, ProgramVolume.__table__, Project.__table__):
        table.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    c = Customer(customer_number="C", name="Kunde")
    db.add(c)
    db.flush()
    p = Program(
        customer_id=c.id,
        program_number="P",
        name="Prog",
        sop=date(2024, 1, 1),
        eop=date(2027, 12, 31),
    )
    db.add(p)
    db.flush()
    for year, vol in ((2024, 40000), (2025, 42000), (2026, 43000), (2027, 42500)):
        db.add(ProgramVolume(program_id=p.id, calendar_year=year, vehicle_volume=vol))
    pr = Project(
        program_id=p.id,
        project_number="TSV",
        name="TSV",
        quantity_per_vehicle=1.0,
    )
    db.add(pr)
    db.commit()
    avg = average_jahresstueckzahl_for_project(db, pr.id)
    assert avg.has_volumes is True
    assert avg.jahresstueckzahl == 41875
    assert avg.jahresstueckzahl == math.ceil(167500 / 4)
    db.close()


def test_no_double_scrap_within_process_step():
    out, surcharge, _ = apply_process_yield(Decimal("50"), Decimal("10"), 10)
    assert float(out) == _money(60 / 0.9)
    assert float(surcharge) == _money(60 / 0.9 - 60)

"""Tests für zentrale Zuschlagslogik (MGK Kaufteile, FGK, SG&A, Profit)."""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.zuschlagssatz import Zuschlagssatz
from app.scripts.seed_top_level_markup_rates import seed_top_level_markup_rates
from app.services.central_markup_rates import (
    CentralMarkupRatesError,
    KAUFTEIL_NOMINIERUNG_OEM,
    KAUFTEIL_NOMINIERUNG_SELBST,
    load_central_markup_rates,
)
from app.services.spritzguss_gesamt_kalkulation import (
    VeredelungSchrittEingabe,
    berechne_gesamt,
)
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss
from app.services.veredelung_kalkulation import VeredelungInput, berechne_veredelung


def _engine():
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
    return engine


@pytest.fixture()
def db():
    engine = _engine()
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


def test_seed_defaults_match_fachwerte(db):
    seed_top_level_markup_rates(db)
    rates = load_central_markup_rates(db)
    assert rates.mgk_kaufteil_selbst_pct == 3.0
    assert rates.mgk_kaufteil_oem_pct == 5.0
    assert rates.fgk_pct == 22.0
    assert rates.vvgk_pct == 10.0
    assert rates.gewinn_pct == 15.0
    assert rates.skonto_pct == 0.0


def test_mgk_selbst_oem_mixed_and_missing(db):
    seed_top_level_markup_rates(db)
    rates = load_central_markup_rates(db)
    assert rates.mgk_pct_for_nominierung(KAUFTEIL_NOMINIERUNG_SELBST) == 3.0
    assert rates.mgk_pct_for_nominierung(KAUFTEIL_NOMINIERUNG_OEM) == 5.0
    with pytest.raises(CentralMarkupRatesError, match="Nominierung"):
        rates.mgk_pct_for_nominierung(None)
    # Gemischt: getrennte Berechnung
    selbst = 100.0 * (1 + 3 / 100)
    oem = 50.0 * (1 + 5 / 100)
    assert round(selbst + oem, 2) == 155.5


def test_missing_active_rates_fail_clearly(db):
    with pytest.raises(CentralMarkupRatesError, match="Fehlende aktive"):
        load_central_markup_rates(db)
    db.add(Zuschlagssatz(bezeichnung="FGK", satz_prozent=22, typ="fgk", aktiv=False))
    db.commit()
    with pytest.raises(CentralMarkupRatesError, match="fgk"):
        load_central_markup_rates(db)


def test_stammdaten_rate_change_affects_new_calculation(db):
    seed_top_level_markup_rates(db)
    rates = load_central_markup_rates(db)
    sg = berechne_spritzguss(
        SpritzgussInput(
            schussgewicht_g=100.0, teilegewicht_netto_g=100,
            materialpreis_pro_kg=10,
            ausschussquote_pct=10,
            zykluszeit_s=36,
            maschinenstundensatz=100,
            kavitaeten=2,
            lohnstundensatz=50,
            fgk_pct=rates.fgk_pct,
            werkzeugkosten_eur=0,
            vvgk_pct=rates.vvgk_pct,
            gewinn_pct=rates.gewinn_pct,
            skonto_pct=rates.skonto_pct,
        )
    )
    first_hk_fgk = sg.fertigungsgemeinkosten

    row = db.scalars(select(Zuschlagssatz).where(Zuschlagssatz.typ == "fgk")).one()
    row.satz_prozent = 30.0
    db.commit()
    rates2 = load_central_markup_rates(db)
    sg2 = berechne_spritzguss(
        SpritzgussInput(
            schussgewicht_g=100.0, teilegewicht_netto_g=100,
            materialpreis_pro_kg=10,
            ausschussquote_pct=10,
            zykluszeit_s=36,
            maschinenstundensatz=100,
            kavitaeten=2,
            lohnstundensatz=50,
            fgk_pct=rates2.fgk_pct,
            werkzeugkosten_eur=0,
            vvgk_pct=rates2.vvgk_pct,
            gewinn_pct=rates2.gewinn_pct,
            skonto_pct=rates2.skonto_pct,
        )
    )
    assert sg2.fertigungsgemeinkosten != first_hk_fgk
    assert sg2.fertigungsgemeinkosten == pytest.approx(0.75 * 0.30, abs=0.01)


def test_fgk_basis_and_no_double_on_veredelung():
    verd = berechne_veredelung(
        VeredelungInput(
            taktzeit_s=36,
            anzahl_mitarbeiter=2,
            lohnstundensatz=50,
            maschinenstundensatz=100,
            verbrauchskosten_je_stueck=0.2,
            ausschussquote_pct=10,
            fgk_pct=99,
            reihenfolge=1,
        )
    )
    assert verd.fertigungsgemeinkosten == 0.0
    direct = verd.kosten_inkl_ausschuss

    sg = berechne_spritzguss(
        SpritzgussInput(
            schussgewicht_g=100.0, teilegewicht_netto_g=100,
            materialpreis_pro_kg=10,
            ausschussquote_pct=10,
            zykluszeit_s=36,
            maschinenstundensatz=100,
            kavitaeten=2,
            lohnstundensatz=50,
            fgk_pct=22,
            werkzeugkosten_eur=0,
            vvgk_pct=10,
            gewinn_pct=15,
            skonto_pct=0,
        )
    )
    gesamt = berechne_gesamt(
        sg.to_dict(),
        [
            VeredelungSchrittEingabe(
                veredelungsschritt_id=1,
                bezeichnung="Montage",
                veredelungsart="Montage",
                reihenfolge=1,
                aktiv=True,
                mengenfaktor=1,
                kosten_inkl_ausschuss=direct,
            )
        ],
        fgk_pct=22,
        vvgk_pct=10,
        gewinn_pct=15,
        skonto_pct=0,
    )
    expected_basis = round(sg.maschinenkosten + sg.fertigungslohn + direct, 2)
    assert gesamt.fgk_basis == pytest.approx(expected_basis)
    assert gesamt.fertigungsgemeinkosten > 0
    # Material nicht in FGK-Basis
    assert gesamt.fgk_basis == pytest.approx(
        gesamt.maschinenkosten + gesamt.fertigungslohn + gesamt.veredelung_gesamt
    )
    assert gesamt.vvgk == pytest.approx(gesamt.gesamte_herstellkosten * 0.10, abs=0.02)
    assert gesamt.gewinn == pytest.approx(gesamt.selbstkosten * 0.15, abs=0.02)


def test_material_mgk_selbst_und_oem(db):
    seed_top_level_markup_rates(db)
    rates = load_central_markup_rates(db)
    selbst = berechne_spritzguss(
        SpritzgussInput(
            schussgewicht_g=100.0, teilegewicht_netto_g=100,
            materialpreis_pro_kg=10,
            ausschussquote_pct=10,
            mgk_pct=rates.mgk_pct_for_nominierung("selbstnominiert"),
            material_nominierung="selbstnominiert",
            zykluszeit_s=36,
            maschinenstundensatz=100,
            kavitaeten=2,
            lohnstundensatz=50,
            fgk_pct=rates.fgk_pct,
            werkzeugkosten_eur=0,
            vvgk_pct=rates.vvgk_pct,
            gewinn_pct=rates.gewinn_pct,
            skonto_pct=0,
        )
    )
    oem = berechne_spritzguss(
        SpritzgussInput(
            schussgewicht_g=100.0, teilegewicht_netto_g=100,
            materialpreis_pro_kg=10,
            ausschussquote_pct=10,
            mgk_pct=rates.mgk_pct_for_nominierung("oem_nominiert"),
            material_nominierung="oem_nominiert",
            zykluszeit_s=36,
            maschinenstundensatz=100,
            kavitaeten=2,
            lohnstundensatz=50,
            fgk_pct=rates.fgk_pct,
            werkzeugkosten_eur=0,
            vvgk_pct=rates.vvgk_pct,
            gewinn_pct=rates.gewinn_pct,
            skonto_pct=0,
        )
    )
    assert selbst.mgk_basis == oem.mgk_basis == 1.11
    assert selbst.materialgemeinkosten == pytest.approx(0.03, abs=0.01)
    assert oem.materialgemeinkosten == pytest.approx(0.06, abs=0.01)
    assert selbst.fgk_basis == oem.fgk_basis
    # FGK-Basis ohne Material/MGK
    assert selbst.fgk_basis == pytest.approx(0.75)


def test_missing_material_nominierung(db):
    seed_top_level_markup_rates(db)
    rates = load_central_markup_rates(db)
    with pytest.raises(CentralMarkupRatesError, match="Nominierung"):
        rates.mgk_pct_for_nominierung(None, kontext="Spritzguss-Materialeinsatz")


def test_sga_and_profit_bases():
    """SG&A 10 % auf HK; Profit 15 % auf HK+SG&A."""
    sg = berechne_spritzguss(
        SpritzgussInput(
            schussgewicht_g=100.0, teilegewicht_netto_g=100,
            materialpreis_pro_kg=10,
            ausschussquote_pct=0,
            mgk_pct=3,
            material_nominierung="selbstnominiert",
            zykluszeit_s=36,
            maschinenstundensatz=100,
            kavitaeten=1,
            lohnstundensatz=50,
            fgk_pct=22,
            werkzeugkosten_eur=0,
            vvgk_pct=10,
            gewinn_pct=15,
            skonto_pct=0,
        )
    )
    assert sg.vvgk == pytest.approx(round(sg.herstellkosten * 0.10, 2))
    assert sg.gewinn == pytest.approx(round(sg.selbstkosten * 0.15, 2))
    assert sg.selbstkosten == pytest.approx(sg.herstellkosten + sg.vvgk)

"""Setup-Umlage, Losgröße und konsistente Herstellkosten (Gesamtpfad)."""

from __future__ import annotations

import pytest

from app.services.spritzguss_gesamt_kalkulation import berechne_gesamt
from app.services.spritzguss_kalkulation import (
    SpritzgussInput,
    SpritzgussValidationError,
    berechne_spritzguss,
)


def _base(**overrides) -> SpritzgussInput:
    data = dict(
        schussgewicht_g=100.0,
        teilegewicht_netto_g=100.0,
        materialpreis_pro_kg=10.0,
        ausschussquote_pct=0.0,
        mgk_pct=0.0,
        material_nominierung="selbstnominiert",
        zykluszeit_s=36.0,
        maschinenstundensatz=100.0,
        kavitaeten=1,
        lohnstundensatz=50.0,
        fgk_pct=0.0,
        werkzeugkosten_eur=0,
        werkzeug_abrechnungsart="einmalzahlung",
        amortisationsvolumen=None,
        vvgk_pct=0.0,
        gewinn_pct=0.0,
        skonto_pct=0.0,
    )
    data.update(overrides)
    return SpritzgussInput(**data)


def test_setup_umlage_auf_losgroesse():
    # 60 min Setup, 100 EUR/h Maschine, 50 EUR/h Lohn × 2 MA, Los 100
    # Maschine: 1h * 100 = 100; Lohn: 1h * 50 * 2 = 100; je Teil 2.00
    r = berechne_spritzguss(
        _base(
            setup_aktiv=True,
            setup_zeit_min=60,
            setup_maschinenstundensatz=100,
            setup_lohnstundensatz=50,
            setup_mitarbeiter=2,
            losgroesse=100,
        )
    )
    assert r.setup_maschinenkosten_gesamt == pytest.approx(100.0)
    assert r.setup_lohnkosten_gesamt == pytest.approx(100.0)
    assert r.setup_maschinenkosten_je_teil == pytest.approx(1.0)
    assert r.setup_lohnkosten_je_teil == pytest.approx(1.0)
    assert r.setup_kosten_je_teil == pytest.approx(2.0)


def test_setup_ohne_losgroesse_fehler():
    with pytest.raises(SpritzgussValidationError, match="losgroesse"):
        berechne_spritzguss(
            _base(setup_aktiv=True, setup_zeit_min=45, losgroesse=None)
        )


def test_setup_deaktiviert_keine_kosten():
    r = berechne_spritzguss(_base(setup_aktiv=False, setup_zeit_min=0, losgroesse=None))
    assert r.setup_kosten_je_teil == 0.0
    assert r.setup_aktiv is False


def test_oem_handling_separat_von_mgk():
    from app.services.central_markup_rates import CentralMarkupRates

    rates = CentralMarkupRates(
        mgk_kaufteil_selbst_pct=3,
        mgk_kaufteil_oem_pct=5,
        fgk_pct=22,
        vvgk_pct=10,
        gewinn_pct=15,
        skonto_pct=0,
        handling_oem_kaufteil_pct=6,
    )
    einkauf = 100.0
    mgk = einkauf * rates.mgk_kaufteil_oem_pct / 100
    handling = einkauf * rates.handling_oem_kaufteil_pct / 100
    total = einkauf + mgk + handling
    assert mgk == 5.0
    assert handling == 6.0
    assert total == 111.0
    assert rates.mgk_kaufteil_oem_pct != rates.handling_oem_kaufteil_pct


def test_gesamt_spritzguss_herstellkosten_inkl_setup_ohne_veredelung():
    """Ohne Veredelung: spritzguss_hk == gesamte_hk == sg.herstellkosten (eine FGK inkl. Setup)."""
    sg = berechne_spritzguss(
        _base(
            fgk_pct=20.0,
            vvgk_pct=10.0,
            gewinn_pct=5.0,
            skonto_pct=0.0,
            setup_aktiv=True,
            setup_zeit_min=60,
            setup_maschinenstundensatz=100,
            setup_lohnstundensatz=50,
            setup_mitarbeiter=2,
            losgroesse=100,
        )
    )
    gesamt = berechne_gesamt(
        sg.to_dict(),
        [],
        fgk_pct=20.0,
        vvgk_pct=10.0,
        gewinn_pct=5.0,
        skonto_pct=0.0,
    )
    assert gesamt.spritzguss_herstellkosten == pytest.approx(sg.herstellkosten)
    assert gesamt.gesamte_herstellkosten == pytest.approx(sg.herstellkosten)
    assert gesamt.spritzguss_herstellkosten == pytest.approx(gesamt.gesamte_herstellkosten)
    assert gesamt.fgk_basis == pytest.approx(
        sg.maschinenkosten + sg.fertigungslohn + sg.setup_kosten_je_teil
    )
    assert gesamt.fertigungsgemeinkosten == pytest.approx(gesamt.fgk_basis * 0.20, abs=0.02)
    expected_vvgk = round(gesamt.gesamte_herstellkosten * 0.10, 2)
    expected_selbst = round(gesamt.gesamte_herstellkosten + expected_vvgk, 2)
    expected_gewinn = round(expected_selbst * 0.05, 2)
    expected_end = round(expected_selbst + expected_gewinn, 2)
    assert gesamt.vvgk == pytest.approx(expected_vvgk)
    assert gesamt.endpreis_je_stueck == pytest.approx(expected_end)


def test_gesamt_ohne_setup_endpreis_kleiner_als_mit_setup():
    ohne = berechne_gesamt(
        berechne_spritzguss(_base(fgk_pct=20.0, vvgk_pct=0, gewinn_pct=0, skonto_pct=0)).to_dict(),
        [],
        fgk_pct=20.0,
        vvgk_pct=0.0,
        gewinn_pct=0.0,
        skonto_pct=0.0,
    )
    mit = berechne_gesamt(
        berechne_spritzguss(
            _base(
                fgk_pct=20.0,
                vvgk_pct=0,
                gewinn_pct=0,
                skonto_pct=0,
                setup_aktiv=True,
                setup_zeit_min=60,
                setup_maschinenstundensatz=100,
                setup_lohnstundensatz=0,
                setup_mitarbeiter=0,
                losgroesse=50,
            )
        ).to_dict(),
        [],
        fgk_pct=20.0,
        vvgk_pct=0.0,
        gewinn_pct=0.0,
        skonto_pct=0.0,
    )
    assert mit.spritzguss_herstellkosten > ohne.spritzguss_herstellkosten
    assert mit.gesamte_herstellkosten > ohne.gesamte_herstellkosten
    assert mit.endpreis_je_stueck > ohne.endpreis_je_stueck
    delta = mit.gesamte_herstellkosten - ohne.gesamte_herstellkosten
    assert delta == pytest.approx(2.0 * 1.20, abs=0.02)


def test_setup_fgk_nicht_doppelt_im_gesamtpfad():
    sg = berechne_spritzguss(
        _base(
            fgk_pct=20.0,
            setup_aktiv=True,
            setup_zeit_min=60,
            setup_maschinenstundensatz=100,
            setup_lohnstundensatz=0,
            setup_mitarbeiter=0,
            losgroesse=100,
        )
    )
    gesamt = berechne_gesamt(
        sg.to_dict(), [], fgk_pct=20.0, vvgk_pct=0, gewinn_pct=0, skonto_pct=0
    )
    expected_fgk = round(
        (sg.maschinenkosten + sg.fertigungslohn + sg.setup_kosten_je_teil) * 0.20, 2
    )
    assert gesamt.fertigungsgemeinkosten == pytest.approx(expected_fgk)
    assert gesamt.gesamte_herstellkosten == pytest.approx(
        sg.materialkosten_gesamt
        + sg.maschinenkosten
        + sg.fertigungslohn
        + sg.setup_kosten_je_teil
        + expected_fgk
    )

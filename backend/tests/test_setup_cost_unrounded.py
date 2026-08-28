"""Setup-Kosten: gemeinsame ungerundete Berechnung ohne Zwischenrundung."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

import pytest

from app.services.spritzguss_gesamt_kalkulation import berechne_gesamt
from app.services.spritzguss_kalkulation import (
    SpritzgussInput,
    _d,
    _money,
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


# Regression aus Excel-Beispiel (Losgröße 2363, Setup 45 min)
REGRESSION = dict(
    setup_maschinenstundensatz=17.511119,
    setup_lohnstundensatz=23.0,
    setup_mitarbeiter=1.0,
    setup_zeit_min=45.0,
    losgroesse=2363,
)


def _setup_je_teil_raw(**params) -> Decimal:
    stunden = _d(params["setup_zeit_min"]) / Decimal("60")
    los = _d(int(params["losgroesse"]))
    stundensatz = _d(params["setup_maschinenstundensatz"]) + (
        _d(params["setup_lohnstundensatz"]) * _d(params["setup_mitarbeiter"])
    )
    return (stundensatz * stunden) / los


def _buggy_setup_je_teil(**params) -> Decimal:
    """Alte Logik: Teilwerte separat runden und addieren."""
    stunden = _d(params["setup_zeit_min"]) / Decimal("60")
    los = _d(int(params["losgroesse"]))
    masch_gesamt = _money(stunden * _d(params["setup_maschinenstundensatz"]))
    lohn_gesamt = _money(
        stunden * _d(params["setup_lohnstundensatz"]) * _d(params["setup_mitarbeiter"])
    )
    masch_teil = _money(masch_gesamt / los)
    lohn_teil = _money(lohn_gesamt / los)
    return _money(masch_teil + lohn_teil)


def test_regression_setup_without_intermediate_rounding():
    raw = _setup_je_teil_raw(**REGRESSION)
    buggy = _buggy_setup_je_teil(**REGRESSION)
    assert raw != buggy
    assert float(buggy) == pytest.approx(0.02)
    assert float(_money(raw)) == pytest.approx(0.01)

    sg = berechne_spritzguss(
        _base(
            setup_aktiv=True,
            fgk_pct=22.0,
            vvgk_pct=10.0,
            gewinn_pct=15.0,
            skonto_pct=0.0,
            **REGRESSION,
        )
    )
    assert sg.setup_kosten_je_teil == pytest.approx(float(raw))
    assert sg.setup_kosten_je_teil != pytest.approx(float(buggy))
    assert sg.setup_maschinenkosten_je_teil == pytest.approx(0.01)
    assert sg.setup_lohnkosten_je_teil == pytest.approx(0.01)
    assert sg.setup_maschinenkosten_je_teil + sg.setup_lohnkosten_je_teil == pytest.approx(
        0.02
    )


def test_fgk_uses_unrounded_setup_total():
    sg = berechne_spritzguss(
        _base(
            setup_aktiv=True,
            fgk_pct=22.0,
            **REGRESSION,
        )
    )
    raw = float(_setup_je_teil_raw(**REGRESSION))
    expected_fgk_basis = float(_money(_d(sg.maschinenkosten) + _d(sg.fertigungslohn) + _d(raw)))
    assert sg.fgk_basis == pytest.approx(expected_fgk_basis)
    buggy_fgk_basis = float(
        _money(
            _d(sg.maschinenkosten)
            + _d(sg.fertigungslohn)
            + _d(float(_buggy_setup_je_teil(**REGRESSION)))
        )
    )
    assert sg.fgk_basis != pytest.approx(buggy_fgk_basis)


def test_gesamt_parity_calculate_save_reload_path():
    sg = berechne_spritzguss(
        _base(
            setup_aktiv=True,
            fgk_pct=22.0,
            vvgk_pct=10.0,
            gewinn_pct=15.0,
            skonto_pct=0.0,
            **REGRESSION,
        )
    )
    gesamt = berechne_gesamt(
        sg.to_dict(),
        [],
        fgk_pct=22.0,
        vvgk_pct=10.0,
        gewinn_pct=15.0,
        skonto_pct=0.0,
    )
    assert gesamt.setup_kosten_je_teil == pytest.approx(sg.setup_kosten_je_teil)
    assert gesamt.fgk_basis == pytest.approx(sg.fgk_basis)


def test_setup_deaktiviert_keine_kosten():
    sg = berechne_spritzguss(_base(setup_aktiv=False, setup_zeit_min=0, losgroesse=None))
    assert sg.setup_kosten_je_teil == 0.0


def test_unterschiedliche_mitarbeiteranzahl():
    sg = berechne_spritzguss(
        _base(
            setup_aktiv=True,
            setup_zeit_min=60,
            setup_maschinenstundensatz=100,
            setup_lohnstundensatz=50,
            setup_mitarbeiter=2,
            losgroesse=100,
        )
    )
    raw = float(
        _setup_je_teil_raw(
            setup_zeit_min=60,
            setup_maschinenstundensatz=100,
            setup_lohnstundensatz=50,
            setup_mitarbeiter=2,
            losgroesse=100,
        )
    )
    assert sg.setup_kosten_je_teil == pytest.approx(raw)
    assert sg.setup_kosten_je_teil == pytest.approx(2.0)


def test_unterschiedliche_losgroessen():
    for los in (100, 2363, 4946):
        params = dict(
            setup_zeit_min=45,
            setup_maschinenstundensatz=17.511119,
            setup_lohnstundensatz=23.0,
            setup_mitarbeiter=1,
            losgroesse=los,
        )
        sg = berechne_spritzguss(_base(setup_aktiv=True, **params))
        assert sg.setup_kosten_je_teil == pytest.approx(float(_setup_je_teil_raw(**params)))

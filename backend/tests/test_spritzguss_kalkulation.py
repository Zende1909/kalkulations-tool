"""Unit-Tests für die Spritzguss-Zuschlagskalkulation."""

import pytest

from app.services.spritzguss_kalkulation import (
    SpritzgussInput,
    SpritzgussValidationError,
    berechne_spritzguss,
    validate_spritzguss_input,
)


def _sample(**overrides) -> SpritzgussInput:
    base = dict(
        teilegewicht_netto_g=100.0,  # 0.1 kg
        materialpreis_pro_kg=10.0,
        ausschussquote_pct=10.0,
        mgk_pct=5.0,
        zykluszeit_s=36.0,  # 0.01 h
        maschinenstundensatz=100.0,
        kavitaeten=2,
        lohnstundensatz=50.0,
        fgk_pct=20.0,
        werkzeugkosten_eur=10000.0,
        werkzeug_abrechnungsart="amortisation",
        amortisationsvolumen=10000,
        vvgk_pct=10.0,
        gewinn_pct=10.0,
        skonto_pct=2.0,
    )
    base.update(overrides)
    return SpritzgussInput(**base)


def test_validate_rejects_negative():
    with pytest.raises(SpritzgussValidationError, match="nicht negativ"):
        validate_spritzguss_input(_sample(materialpreis_pro_kg=-1))


def test_validate_ausschuss_under_100():
    with pytest.raises(SpritzgussValidationError, match="kleiner als 100"):
        validate_spritzguss_input(_sample(ausschussquote_pct=100))


def test_validate_kavitaeten_min_1():
    with pytest.raises(SpritzgussValidationError, match="mindestens 1"):
        validate_spritzguss_input(_sample(kavitaeten=0))


def test_werkzeugfelder_beeinflussen_teilepreis_nicht():
    """Historische Werkzeugwerte werden gespeichert, aber nicht mehr kalkuliert."""
    result_amort = berechne_spritzguss(
        _sample(amortisationsvolumen=1, werkzeugkosten_eur=100)
    )
    assert result_amort.werkzeugkostenanteil == 0.0
    assert result_amort.werkzeug_einmalzahlung == 0.0

    result_einmal = berechne_spritzguss(
        _sample(
            werkzeug_abrechnungsart="einmalzahlung",
            amortisationsvolumen=None,
            werkzeugkosten_eur=5000,
        )
    )
    assert result_einmal.werkzeugkostenanteil == 0.0
    assert result_einmal.werkzeug_einmalzahlung == 0.0
    assert result_einmal.herstellkosten == result_amort.herstellkosten


def test_teilepreis_ohne_investitionsanteil():
    result = berechne_spritzguss(_sample())
    assert result.werkzeugkostenanteil == 0.0
    assert result.herstellkosten == 1.97
    assert result.verkaufspreis == pytest.approx(2.44, abs=0.01)


def test_stufe_1_materialgewicht():
    result = berechne_spritzguss(_sample(teilegewicht_netto_g=100))
    assert result.materialgewicht_kg == 0.1


def test_stufe_2_materialkosten():
    result = berechne_spritzguss(_sample())
    assert result.materialkosten == 1.0


def test_stufe_3_materialkosten_inkl_ausschuss():
    result = berechne_spritzguss(_sample())
    assert result.materialkosten_inkl_ausschuss == 1.11


def test_stufe_4_materialgemeinkosten():
    result = berechne_spritzguss(_sample())
    assert result.materialgemeinkosten == 0.06


def test_stufe_5_materialkosten_gesamt():
    result = berechne_spritzguss(_sample())
    assert result.materialkosten_gesamt == 1.17


def test_stufe_6_maschinenkosten():
    result = berechne_spritzguss(_sample())
    assert result.maschinenkosten == 0.5


def test_stufe_7_fertigungslohn():
    result = berechne_spritzguss(_sample())
    assert result.fertigungslohn == 0.25


def test_stufe_8_fertigungsgemeinkosten():
    result = berechne_spritzguss(_sample())
    assert result.fertigungsgemeinkosten == 0.05


def test_stufe_9_werkzeugkostenanteil_null():
    result = berechne_spritzguss(_sample())
    assert result.werkzeugkostenanteil == 0.0


def test_stufe_10_herstellkosten():
    result = berechne_spritzguss(_sample())
    assert result.herstellkosten == 1.97


def test_stufe_11_vvgk():
    result = berechne_spritzguss(_sample())
    assert result.vvgk == 0.20


def test_stufe_12_selbstkosten():
    result = berechne_spritzguss(_sample())
    assert result.selbstkosten == 2.17


def test_stufe_13_gewinn():
    result = berechne_spritzguss(_sample())
    assert result.gewinn == 0.22


def test_stufe_14_nettoverkaufspreis():
    result = berechne_spritzguss(_sample())
    assert result.nettoverkaufspreis == 2.39


def test_stufe_15_skonto():
    result = berechne_spritzguss(_sample())
    assert result.skonto == 0.05


def test_stufe_16_verkaufspreis():
    result = berechne_spritzguss(_sample())
    assert result.verkaufspreis == 2.44


def test_as_blocks_structure():
    blocks = berechne_spritzguss(_sample()).as_blocks()
    assert set(blocks.keys()) == {
        "material",
        "fertigung",
        "werkzeug",
        "gemeinkosten",
        "verkaufspreis",
    }
    assert blocks["werkzeug"]["werkzeugkostenanteil"] == 0.0
    assert blocks["werkzeug"]["werkzeug_einmalzahlung"] == 0.0

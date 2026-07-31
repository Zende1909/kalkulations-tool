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
        amortisationsvolumen=10000.0,
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


def test_validate_amortisation_gt_0():
    with pytest.raises(SpritzgussValidationError, match="größer als 0"):
        validate_spritzguss_input(_sample(amortisationsvolumen=0))


def test_stufe_1_materialgewicht():
    # 100 g → 0.1 kg
    result = berechne_spritzguss(_sample(teilegewicht_netto_g=100))
    assert result.materialgewicht_kg == 0.1


def test_stufe_2_materialkosten():
    # 0.1 kg × 10 €/kg = 1.00
    result = berechne_spritzguss(_sample())
    assert result.materialkosten == 1.0


def test_stufe_3_materialkosten_inkl_ausschuss():
    # 1.00 / (1 - 0.10) = 1.111... → 1.11
    result = berechne_spritzguss(_sample())
    assert result.materialkosten_inkl_ausschuss == 1.11


def test_stufe_4_materialgemeinkosten():
    # 1.11 × 0.05 = 0.0555 → 0.06
    result = berechne_spritzguss(_sample())
    assert result.materialgemeinkosten == 0.06


def test_stufe_5_materialkosten_gesamt():
    # 1.11 + 0.06 = 1.17
    result = berechne_spritzguss(_sample())
    assert result.materialkosten_gesamt == 1.17


def test_stufe_6_maschinenkosten():
    # 36/3600 × 100 / 2 = 0.01 × 100 / 2 = 0.50
    result = berechne_spritzguss(_sample())
    assert result.maschinenkosten == 0.5


def test_stufe_7_fertigungslohn():
    # 36/3600 × 50 / 2 = 0.25
    result = berechne_spritzguss(_sample())
    assert result.fertigungslohn == 0.25


def test_stufe_8_fertigungsgemeinkosten():
    # 0.25 × 0.20 = 0.05
    result = berechne_spritzguss(_sample())
    assert result.fertigungsgemeinkosten == 0.05


def test_stufe_9_werkzeugkostenanteil():
    # 10000 / 10000 = 1.00
    result = berechne_spritzguss(_sample())
    assert result.werkzeugkostenanteil == 1.0


def test_stufe_10_herstellkosten():
    # 1.17 + 0.50 + 0.25 + 0.05 + 1.00 = 2.97
    result = berechne_spritzguss(_sample())
    assert result.herstellkosten == 2.97


def test_stufe_11_vvgk():
    # 2.97 × 0.10 = 0.297 → 0.30
    result = berechne_spritzguss(_sample())
    assert result.vvgk == 0.30


def test_stufe_12_selbstkosten():
    # 2.97 + 0.30 = 3.27
    result = berechne_spritzguss(_sample())
    assert result.selbstkosten == 3.27


def test_stufe_13_gewinn():
    # 3.27 × 0.10 = 0.327 → 0.33
    result = berechne_spritzguss(_sample())
    assert result.gewinn == 0.33


def test_stufe_14_nettoverkaufspreis():
    # 3.27 + 0.33 = 3.60
    result = berechne_spritzguss(_sample())
    assert result.nettoverkaufspreis == 3.60


def test_stufe_15_skonto():
    # 3.60 × 0.02 = 0.072 → 0.07
    result = berechne_spritzguss(_sample())
    assert result.skonto == 0.07


def test_stufe_16_verkaufspreis():
    # 3.60 + 0.07 = 3.67
    result = berechne_spritzguss(_sample())
    assert result.verkaufspreis == 3.67


def test_as_blocks_structure():
    blocks = berechne_spritzguss(_sample()).as_blocks()
    assert set(blocks.keys()) == {
        "material",
        "fertigung",
        "werkzeug",
        "gemeinkosten",
        "verkaufspreis",
    }

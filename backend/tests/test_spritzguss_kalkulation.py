"""Unit-Tests für die Spritzguss-Zuschlagskalkulation (Material-MGK + FGK)."""

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
        mgk_pct=5.0,  # OEM-Satz
        material_nominierung="oem_nominiert",
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
    result_amort = berechne_spritzguss(
        _sample(amortisationsvolumen=1, werkzeugkosten_eur=100)
    )
    assert result_amort.werkzeugkostenanteil == 0.0
    result_einmal = berechne_spritzguss(
        _sample(
            werkzeug_abrechnungsart="einmalzahlung",
            amortisationsvolumen=None,
            werkzeugkosten_eur=5000,
        )
    )
    assert result_einmal.herstellkosten == result_amort.herstellkosten


def test_material_mgk_oem_5_pct_auf_inkl_ausschuss():
    """MGK-Basis = Materialkosten inklusive Ausschuss."""
    result = berechne_spritzguss(_sample(mgk_pct=5))
    assert result.materialkosten == 1.0
    assert result.materialkosten_inkl_ausschuss == 1.11
    assert result.mgk_basis == 1.11
    assert result.materialgemeinkosten == 0.06
    assert result.materialkosten_gesamt == 1.17


def test_material_mgk_selbst_3_pct():
    result = berechne_spritzguss(
        _sample(mgk_pct=3, material_nominierung="selbstnominiert")
    )
    assert result.mgk_basis == 1.11
    assert result.materialgemeinkosten == pytest.approx(0.03, abs=0.01)
    assert result.applied_mgk_pct == 3.0


def test_fgk_nicht_auf_material_oder_mgk():
    result = berechne_spritzguss(_sample(fgk_pct=22, mgk_pct=5))
    assert result.fgk_basis == 0.75  # nur Maschine + Lohn
    assert result.fertigungsgemeinkosten == pytest.approx(0.17, abs=0.01)
    assert result.materialkosten_gesamt == 1.17  # inkl. MGK, nicht in FGK-Basis


def test_stufe_herstellkosten_mit_mgk_und_fgk():
    # material 1.17 + machine 0.5 + lohn 0.25 + fgk 0.15 = 2.07
    result = berechne_spritzguss(_sample())
    assert result.herstellkosten == 2.07
    assert result.vvgk == 0.21
    assert result.selbstkosten == 2.28
    assert result.gewinn == 0.23
    assert result.nettoverkaufspreis == 2.51
    assert result.skonto == 0.05
    assert result.verkaufspreis == 2.56


def test_as_blocks_zeigt_mgk_basis():
    blocks = berechne_spritzguss(_sample()).as_blocks()
    assert blocks["material"]["mgk_basis"] == 1.11
    assert blocks["material"]["materialgemeinkosten"] == 0.06
    assert blocks["fertigung"]["fgk_basis"] == 0.75

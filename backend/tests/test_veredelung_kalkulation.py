"""Unit-Tests für die Veredelungs-Kostenberechnung."""

import pytest

from app.services.veredelung_kalkulation import (
    VeredelungInput,
    VeredelungValidationError,
    berechne_veredelung,
    validate_veredelung_input,
)


def _sample(**overrides) -> VeredelungInput:
    base = dict(
        taktzeit_s=36.0,  # 0.01 h
        anzahl_mitarbeiter=2,
        lohnstundensatz=50.0,
        maschinenstundensatz=100.0,
        verbrauchskosten_je_stueck=0.20,
        ausschussquote_pct=10.0,
        fgk_pct=20.0,
        reihenfolge=1,
    )
    base.update(overrides)
    return VeredelungInput(**base)


def test_lohnkosten_je_stueck():
    # 36/3600 * 50 * 2 = 1.00
    result = berechne_veredelung(_sample())
    assert result.lohnkosten_je_stueck == 1.0


def test_maschinenkosten_je_stueck():
    # 36/3600 * 100 = 1.00
    result = berechne_veredelung(_sample())
    assert result.maschinenkosten_je_stueck == 1.0


def test_fertigungsgemeinkosten():
    # 1.00 * 0.20 = 0.20
    result = berechne_veredelung(_sample())
    assert result.fertigungsgemeinkosten == 0.2


def test_kosten_vor_ausschuss():
    # 1.00 + 1.00 + 0.20 + 0.20 = 2.40
    result = berechne_veredelung(_sample())
    assert result.kosten_vor_ausschuss == 2.4


def test_kosten_inkl_ausschuss():
    # 2.40 / 0.9 = 2.666... → 2.67
    result = berechne_veredelung(_sample())
    assert result.kosten_inkl_ausschuss == 2.67


def test_ohne_maschinenstundensatz():
    result = berechne_veredelung(_sample(maschinenstundensatz=None))
    assert result.maschinenkosten_je_stueck == 0.0
    # 1.00 + 0 + 0.20 + 0.20 = 1.40; /0.9 = 1.555... → 1.56
    assert result.kosten_vor_ausschuss == 1.4
    assert result.kosten_inkl_ausschuss == 1.56


def test_taktzeit_negativ_invalid():
    with pytest.raises(VeredelungValidationError, match="nicht negativ"):
        validate_veredelung_input(_sample(taktzeit_s=-1))


def test_mitarbeiter_min_1():
    with pytest.raises(VeredelungValidationError, match="mindestens 1"):
        validate_veredelung_input(_sample(anzahl_mitarbeiter=0))


def test_ausschuss_unter_100():
    with pytest.raises(VeredelungValidationError, match="< 100"):
        validate_veredelung_input(_sample(ausschussquote_pct=100))


def test_ausschuss_nicht_negativ():
    with pytest.raises(VeredelungValidationError, match=">= 0"):
        validate_veredelung_input(_sample(ausschussquote_pct=-1))


def test_lohnstundensatz_nicht_negativ():
    with pytest.raises(VeredelungValidationError, match="lohnstundensatz"):
        validate_veredelung_input(_sample(lohnstundensatz=-1))


def test_maschinenstundensatz_nicht_negativ():
    with pytest.raises(VeredelungValidationError, match="maschinenstundensatz"):
        validate_veredelung_input(_sample(maschinenstundensatz=-5))


def test_verbrauch_nicht_negativ():
    with pytest.raises(VeredelungValidationError, match="verbrauchskosten"):
        validate_veredelung_input(_sample(verbrauchskosten_je_stueck=-0.1))


def test_fgk_nicht_negativ():
    with pytest.raises(VeredelungValidationError, match="fgk_pct"):
        validate_veredelung_input(_sample(fgk_pct=-1))


def test_reihenfolge_muss_positiv_sein():
    with pytest.raises(VeredelungValidationError, match="reihenfolge"):
        validate_veredelung_input(_sample(reihenfolge=0))


def test_reihenfolge_keine_dezimalzahl():
    with pytest.raises(VeredelungValidationError, match="reihenfolge"):
        validate_veredelung_input(_sample(reihenfolge=1.5))  # type: ignore[arg-type]

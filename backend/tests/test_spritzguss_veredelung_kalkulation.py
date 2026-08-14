"""Unit-Tests für Spritzguss + Veredelung Gesamtkalkulation."""

import pytest

from app.services.spritzguss_gesamt_kalkulation import (
    GesamtValidationError,
    VeredelungSchrittEingabe,
    berechne_gesamt,
    berechne_veredelung_schritt,
)
from app.services.spritzguss_kalkulation import berechne_spritzguss, SpritzgussInput


DEFAULT_RATES = dict(vvgk_pct=10.0, gewinn_pct=10.0, skonto_pct=2.0)


def _spritzguss(**overrides) -> dict:
    base = dict(
        teilegewicht_netto_g=100.0,
        materialpreis_pro_kg=10.0,
        ausschussquote_pct=10.0,
        mgk_pct=5.0,
        zykluszeit_s=36.0,
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
    return berechne_spritzguss(SpritzgussInput(**base)).to_dict()


def _veredelung(schritt_id: int, kosten: float, **overrides) -> VeredelungSchrittEingabe:
    base = dict(
        veredelungsschritt_id=schritt_id,
        bezeichnung=f"Schritt {schritt_id}",
        veredelungsart="Montage",
        reihenfolge=schritt_id,
        aktiv=True,
        mengenfaktor=1.0,
        kosten_inkl_ausschuss=kosten,
    )
    base.update(overrides)
    return VeredelungSchrittEingabe(**base)


def _expected_endpreis(
    herstellkosten_mit_werkzeug: float,
    veredelung_gesamt: float,
    *,
    vvgk_pct: float = 10.0,
    gewinn_pct: float = 10.0,
    skonto_pct: float = 2.0,
) -> float:
    """Erwarteter Endpreis nach Zuschlagskette auf gesamte Herstellkosten."""
    hk = round(herstellkosten_mit_werkzeug + veredelung_gesamt, 2)
    vvgk = round(hk * vvgk_pct / 100, 2)
    selbst = round(hk + vvgk, 2)
    gewinn = round(selbst * gewinn_pct / 100, 2)
    netto = round(selbst + gewinn, 2)
    skonto = round(netto * skonto_pct / 100, 2)
    return round(netto + skonto, 2)


def test_ohne_veredelung():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [], **DEFAULT_RATES)
    assert result.veredelung_gesamt == 0.0
    assert result.endpreis_je_stueck == pytest.approx(sg["verkaufspreis"])
    assert result.spritzguss_verkaufspreis == pytest.approx(sg["verkaufspreis"])
    assert result.vvgk == pytest.approx(sg["vvgk"])
    assert result.gewinn == pytest.approx(sg["gewinn"])


def test_mit_einem_veredelungsschritt():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [_veredelung(1, 2.67)], **DEFAULT_RATES)
    assert result.veredelung_gesamt == 2.67
    expected = _expected_endpreis(sg["herstellkosten"], 2.67)
    assert result.endpreis_je_stueck == pytest.approx(expected)
    assert result.endpreis_je_stueck != pytest.approx(sg["verkaufspreis"] + 2.67)
    assert len(result.veredelung_schritte) == 1


def test_mit_mehreren_schritten():
    sg = _spritzguss()
    result = berechne_gesamt(
        sg,
        [
            _veredelung(1, 1.0, reihenfolge=2),
            _veredelung(2, 2.0, reihenfolge=1),
        ],
        **DEFAULT_RATES,
    )
    assert result.veredelung_gesamt == 3.0
    assert [s.reihenfolge for s in result.veredelung_schritte] == [1, 2]
    expected = _expected_endpreis(sg["herstellkosten"], 3.0)
    assert result.endpreis_je_stueck == pytest.approx(expected)


def test_reihenfolge_aendert_nur_anzeige_nicht_summe():
    sg = _spritzguss()
    a = berechne_gesamt(
        sg,
        [_veredelung(1, 1.0, reihenfolge=1), _veredelung(2, 2.0, reihenfolge=2)],
        **DEFAULT_RATES,
    )
    b = berechne_gesamt(
        sg,
        [_veredelung(1, 1.0, reihenfolge=2), _veredelung(2, 2.0, reihenfolge=1)],
        **DEFAULT_RATES,
    )
    assert a.veredelung_gesamt == b.veredelung_gesamt == 3.0
    assert a.endpreis_je_stueck == pytest.approx(b.endpreis_je_stueck)


def test_entfernen_durch_leere_liste():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [], **DEFAULT_RATES)
    assert result.veredelung_gesamt == 0.0
    assert result.endpreis_je_stueck == pytest.approx(sg["verkaufspreis"])


def test_inaktive_zuordnung_wird_nicht_summiert():
    sg = _spritzguss()
    result = berechne_gesamt(
        sg,
        [_veredelung(1, 5.0, aktiv=False), _veredelung(2, 2.0, aktiv=True)],
        **DEFAULT_RATES,
    )
    assert result.veredelung_gesamt == 2.0
    assert result.veredelung_schritte[0].kosten_gesamt == 0.0


def test_keine_doppelte_addition():
    sg = _spritzguss()
    with pytest.raises(GesamtValidationError, match="doppelt"):
        berechne_gesamt(sg, [_veredelung(1, 1.0), _veredelung(1, 2.0)], **DEFAULT_RATES)


def test_einmalzahlung_bleibt_separat():
    sg = _spritzguss(
        werkzeug_abrechnungsart="einmalzahlung",
        amortisationsvolumen=None,
        werkzeugkosten_eur=5000,
    )
    result = berechne_gesamt(sg, [_veredelung(1, 1.0)], **DEFAULT_RATES)
    assert result.werkzeug_einmalzahlung == 5000.0
    assert result.werkzeugkostenanteil == 0.0
    expected = _expected_endpreis(sg["herstellkosten"], 1.0)
    assert result.endpreis_je_stueck == pytest.approx(expected)
    assert result.endpreis_je_stueck != pytest.approx(sg["verkaufspreis"] + 1.0)


def test_mengenfaktor():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [_veredelung(1, 2.0, mengenfaktor=2.0)], **DEFAULT_RATES)
    assert result.veredelung_gesamt == 4.0


def test_mengenfaktor_negativ_invalid():
    with pytest.raises(GesamtValidationError, match="mengenfaktor"):
        berechne_veredelung_schritt(_veredelung(1, 1.0, mengenfaktor=-1))


def test_vvgk_auf_gesamt_herstellkosten():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [_veredelung(1, 2.67)], **DEFAULT_RATES)
    expected_vvgk = round(result.gesamte_herstellkosten * 0.10, 2)
    assert result.vvgk == pytest.approx(expected_vvgk)
    assert result.vvgk != pytest.approx(sg["vvgk"])


def test_gewinn_auf_selbstkosten_mit_veredelung():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [_veredelung(1, 2.67)], **DEFAULT_RATES)
    expected_gewinn = round(result.selbstkosten * 0.10, 2)
    assert result.gewinn == pytest.approx(expected_gewinn)
    assert result.selbstkosten == pytest.approx(result.gesamte_herstellkosten + result.vvgk)


def test_ergebnisuebersicht_mit_werkzeuganteil():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [_veredelung(1, 1.0)], **DEFAULT_RATES)
    overview = result.as_ergebnisuebersicht()
    assert overview["werkzeugkostenanteil"] == pytest.approx(sg["werkzeugkostenanteil"])
    assert overview["gesamte_herstellkosten"] == pytest.approx(
        sg["herstellkosten"] + 1.0
    )
    assert overview["spritzguss_herstellkosten"] == pytest.approx(
        sg["herstellkosten"] - sg["werkzeugkostenanteil"]
    )

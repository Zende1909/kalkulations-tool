"""Unit-Tests für Spritzguss + Veredelung Gesamtkalkulation."""

import pytest

from app.services.spritzguss_gesamt_kalkulation import (
    GesamtValidationError,
    VeredelungSchrittEingabe,
    berechne_gesamt,
    berechne_veredelung_schritt,
)
from app.services.spritzguss_kalkulation import berechne_spritzguss, SpritzgussInput


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


def test_ohne_veredelung():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [])
    assert result.veredelung_gesamt == 0.0
    assert result.endpreis_je_stueck == pytest.approx(sg["verkaufspreis"])
    assert result.spritzguss_verkaufspreis == pytest.approx(sg["verkaufspreis"])


def test_mit_einem_veredelungsschritt():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [_veredelung(1, 2.67)])
    assert result.veredelung_gesamt == 2.67
    assert result.endpreis_je_stueck == pytest.approx(sg["verkaufspreis"] + 2.67)
    assert len(result.veredelung_schritte) == 1


def test_mit_mehreren_schritten():
    sg = _spritzguss()
    result = berechne_gesamt(
        sg,
        [
            _veredelung(1, 1.0, reihenfolge=2),
            _veredelung(2, 2.0, reihenfolge=1),
        ],
    )
    assert result.veredelung_gesamt == 3.0
    assert [s.reihenfolge for s in result.veredelung_schritte] == [1, 2]


def test_reihenfolge_aendert_nur_anzeige_nicht_summe():
    sg = _spritzguss()
    a = berechne_gesamt(sg, [_veredelung(1, 1.0, reihenfolge=1), _veredelung(2, 2.0, reihenfolge=2)])
    b = berechne_gesamt(sg, [_veredelung(1, 1.0, reihenfolge=2), _veredelung(2, 2.0, reihenfolge=1)])
    assert a.veredelung_gesamt == b.veredelung_gesamt == 3.0


def test_entfernen_durch_leere_liste():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [])
    assert result.veredelung_gesamt == 0.0


def test_inaktive_zuordnung_wird_nicht_summiert():
    sg = _spritzguss()
    result = berechne_gesamt(
        sg,
        [_veredelung(1, 5.0, aktiv=False), _veredelung(2, 2.0, aktiv=True)],
    )
    assert result.veredelung_gesamt == 2.0
    assert result.veredelung_schritte[0].kosten_gesamt == 0.0


def test_keine_doppelte_addition():
    sg = _spritzguss()
    with pytest.raises(GesamtValidationError, match="doppelt"):
        berechne_gesamt(sg, [_veredelung(1, 1.0), _veredelung(1, 2.0)])


def test_einmalzahlung_bleibt_separat():
    sg = _spritzguss(
        werkzeug_abrechnungsart="einmalzahlung",
        amortisationsvolumen=None,
        werkzeugkosten_eur=5000,
    )
    result = berechne_gesamt(sg, [_veredelung(1, 1.0)])
    assert result.werkzeug_einmalzahlung == 5000.0
    assert result.werkzeugkostenanteil == 0.0
    assert result.endpreis_je_stueck == pytest.approx(sg["verkaufspreis"] + 1.0)


def test_mengenfaktor():
    sg = _spritzguss()
    result = berechne_gesamt(sg, [_veredelung(1, 2.0, mengenfaktor=2.0)])
    assert result.veredelung_gesamt == 4.0


def test_mengenfaktor_negativ_invalid():
    with pytest.raises(GesamtValidationError, match="mengenfaktor"):
        berechne_veredelung_schritt(_veredelung(1, 1.0, mengenfaktor=-1))

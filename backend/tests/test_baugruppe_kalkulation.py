"""Unit-Tests für Baugruppenkalkulation."""

import pytest

from app.services.baugruppe_kalkulation import (
    BaugruppeValidationError,
    EinzelteilEingabe,
    InvestitionAnzeige,
    KaufteilEingabe,
    VeredelungEingabe,
    berechne_baugruppe,
)


def _einzelteil(sid: int, preis: float, menge: float = 1.0, **kw) -> EinzelteilEingabe:
    base = dict(
        spritzguss_kalkulation_id=sid,
        bezeichnung=f"Teil {sid}",
        teilenummer=f"T-{sid}",
        menge=menge,
        reihenfolge=sid,
        snapshot_preis=preis,
    )
    base.update(kw)
    return EinzelteilEingabe(**base)


def _kaufteil(kid: int, preis: float, menge: float = 1.0, **kw) -> KaufteilEingabe:
    base = dict(
        kaufteil_id=kid,
        bezeichnung=f"Kaufteil {kid}",
        lieferant="Lieferant A",
        menge=menge,
        reihenfolge=kid,
        snapshot_preis=preis,
    )
    base.update(kw)
    return KaufteilEingabe(**base)


def _veredelung(vid: int, kosten: float, faktor: float = 1.0, **kw) -> VeredelungEingabe:
    base = dict(
        veredelungsschritt_id=vid,
        bezeichnung=f"Montage {vid}",
        reihenfolge=vid,
        mengenfaktor=faktor,
        snapshot_kosten=kosten,
    )
    base.update(kw)
    return VeredelungEingabe(**base)


def test_ohne_positionen():
    result = berechne_baugruppe([], [], [], jahresstueckzahl=1000)
    assert result.baugruppenpreis_je_stueck == 0.0
    assert result.jahresumsatz == 0.0


def test_mit_einem_einzelteil():
    result = berechne_baugruppe([_einzelteil(1, 5.50, menge=2)], [], [])
    assert result.einzelteile_gesamt == pytest.approx(11.0)
    assert result.baugruppenpreis_je_stueck == pytest.approx(11.0)


def test_mit_mehreren_einzelteilen():
    result = berechne_baugruppe(
        [_einzelteil(1, 3.0), _einzelteil(2, 4.0, reihenfolge=2)],
        [],
        [],
    )
    assert result.einzelteile_gesamt == pytest.approx(7.0)
    assert result.baugruppenpreis_je_stueck == pytest.approx(7.0)


def test_kaufteil_hinzufuegen():
    result = berechne_baugruppe([], [_kaufteil(1, 2.50, menge=3)], [])
    assert result.kaufteile_gesamt == pytest.approx(7.50)
    assert result.baugruppenpreis_je_stueck == pytest.approx(7.50)


def test_kaufteilpreis_ueberschreiben():
    result = berechne_baugruppe([], [_kaufteil(1, 9.99)], [])
    assert result.kaufteile[0].einzelpreis == pytest.approx(9.99)


def test_veredelungsschritt_hinzufuegen():
    result = berechne_baugruppe([], [], [_veredelung(1, 1.20)])
    assert result.veredelung_gesamt == pytest.approx(1.20)


def test_reihenfolge_aendert_summe_nicht():
    a = berechne_baugruppe(
        [],
        [],
        [_veredelung(1, 1.0, reihenfolge=2), _veredelung(2, 2.0, reihenfolge=1)],
    )
    b = berechne_baugruppe(
        [],
        [],
        [_veredelung(1, 1.0, reihenfolge=1), _veredelung(2, 2.0, reihenfolge=2)],
    )
    assert a.veredelung_gesamt == b.veredelung_gesamt == 3.0


def test_menge_aendert_zwischensumme():
    result = berechne_baugruppe([_einzelteil(1, 5.0, menge=4)], [], [])
    assert result.einzelteile[0].zwischensumme == pytest.approx(20.0)


def test_investition_separat_anzeigen():
    inv = InvestitionAnzeige(
        id=1,
        bezeichnung="Werkzeug XY",
        investment_type="Werkzeug",
        amount=15000.0,
        status="offen",
        quelle="Einzelteil",
    )
    result = berechne_baugruppe([_einzelteil(1, 10.0)], [], [], investitionen=[inv])
    assert result.investitionen_gesamt == 15000.0
    assert len(result.investitionen) == 1


def test_investition_nicht_im_stueckpreis():
    inv = InvestitionAnzeige(
        id=1,
        bezeichnung="Werkzeug",
        investment_type="Werkzeug",
        amount=50000.0,
        status="offen",
        quelle="Einzelteil",
    )
    result = berechne_baugruppe([_einzelteil(1, 10.0)], [], [], investitionen=[inv])
    assert result.baugruppenpreis_je_stueck == pytest.approx(10.0)


def test_gesamtkalkulation():
    result = berechne_baugruppe(
        [_einzelteil(1, 10.0, menge=2)],
        [_kaufteil(1, 3.0)],
        [_veredelung(1, 2.0, faktor=1.5)],
        jahresstueckzahl=5000,
    )
    assert result.baugruppenpreis_je_stueck == pytest.approx(10 * 2 + 3 + 2 * 1.5)
    assert result.jahresumsatz == pytest.approx(result.baugruppenpreis_je_stueck * 5000)


def test_preis_snapshots_bleiben_berechnungsbasis():
    result = berechne_baugruppe([_einzelteil(1, 7.77)], [], [])
    assert result.einzelteile[0].einzelpreis == pytest.approx(7.77)


def test_ungueltige_menge():
    with pytest.raises(BaugruppeValidationError, match="Menge"):
        berechne_baugruppe([_einzelteil(1, 5.0, menge=0)], [], [])


def test_ungueltiger_mengenfaktor():
    with pytest.raises(BaugruppeValidationError, match="Mengenfaktor"):
        berechne_baugruppe([], [], [_veredelung(1, 1.0, faktor=0)])


def test_doppeltes_einzelteil():
    with pytest.raises(BaugruppeValidationError, match="doppelt"):
        berechne_baugruppe([_einzelteil(1, 1.0), _einzelteil(1, 2.0, reihenfolge=2)], [], [])

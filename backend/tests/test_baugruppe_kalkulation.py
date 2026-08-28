"""Unit-Tests für Baugruppenkalkulation."""

import pytest

from app.services.baugruppe_kalkulation import (
    BaugruppeMarkupError,
    BaugruppeValidationError,
    EinzelteilEingabe,
    InvestitionAnzeige,
    KaufteilEingabe,
    VeredelungEingabe,
    berechne_baugruppe,
)
from app.services.process_yield import apply_process_yield

GEWINN_PCT = 15.0


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


def _veredelung(
    vid: int,
    kosten: float,
    faktor: float = 1.0,
    ausschussquote_pct: float = 0.0,
    **kw,
) -> VeredelungEingabe:
    base = dict(
        veredelungsschritt_id=vid,
        bezeichnung=f"Montage {vid}",
        reihenfolge=vid,
        mengenfaktor=faktor,
        kosten_vor_ausschuss=kosten,
        ausschussquote_pct=ausschussquote_pct,
        snapshot_kosten=kosten,
    )
    base.update(kw)
    return VeredelungEingabe(**base)


def _calc(*args, **kwargs):
    kwargs.setdefault("gewinn_pct", GEWINN_PCT)
    return berechne_baugruppe(*args, **kwargs)


def test_ohne_positionen():
    result = _calc([], [], [], jahresstueckzahl=1000)
    assert result.baugruppenpreis_je_stueck == 0.0
    assert result.jahresumsatz == 0.0


def test_mit_einem_einzelteil():
    result = _calc([_einzelteil(1, 5.50, menge=2)], [], [])
    assert result.einzelteile_gesamt == pytest.approx(11.0)
    assert result.vorprodukt_gesamt == pytest.approx(11.0)
    assert result.baugruppenpreis_je_stueck == pytest.approx(11.0 * 1.15, abs=0.01)


def test_mit_mehreren_einzelteilen():
    result = _calc([_einzelteil(1, 3.0), _einzelteil(2, 4.0, reihenfolge=2)], [], [])
    assert result.einzelteile_gesamt == pytest.approx(7.0)
    assert result.baugruppenpreis_je_stueck == pytest.approx(7.0 * 1.15, abs=0.01)


def test_kaufteil_hinzufuegen():
    result = _calc([], [_kaufteil(1, 2.50, menge=3)], [])
    assert result.kaufteile_gesamt == pytest.approx(7.50)
    assert result.baugruppenpreis_je_stueck == pytest.approx(8.63)


def test_kaufteilpreis_ueberschreiben():
    result = _calc([], [_kaufteil(1, 9.99)], [])
    assert result.kaufteile[0].einzelpreis == pytest.approx(9.99)


def test_veredelungsschritt_hinzufuegen():
    result = _calc([], [], [_veredelung(1, 1.20)])
    assert result.veredelung_gesamt == pytest.approx(1.20)
    assert result.baugruppenpreis_je_stueck == pytest.approx(1.20 * 1.15, abs=0.01)


def test_reihenfolge_aendert_summe_nicht():
    a = _calc(
        [],
        [],
        [_veredelung(1, 1.0, reihenfolge=2), _veredelung(2, 2.0, reihenfolge=1)],
    )
    b = _calc(
        [],
        [],
        [_veredelung(1, 1.0, reihenfolge=1), _veredelung(2, 2.0, reihenfolge=2)],
    )
    assert a.veredelung_gesamt == b.veredelung_gesamt == 3.0
    assert a.baugruppenpreis_je_stueck == b.baugruppenpreis_je_stueck == pytest.approx(3.0 * 1.15, abs=0.01)


def test_menge_aendert_zwischensumme():
    result = _calc([_einzelteil(1, 5.0, menge=4)], [], [])
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
    result = _calc([_einzelteil(1, 10.0)], [], [], investitionen=[inv])
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
    result = _calc([_einzelteil(1, 10.0)], [], [], investitionen=[inv])
    assert result.baugruppenpreis_je_stueck == pytest.approx(10.0 * 1.15, abs=0.01)


def test_gesamtkalkulation():
    result = _calc(
        [_einzelteil(1, 10.0, menge=2)],
        [_kaufteil(1, 3.0)],
        [_veredelung(1, 2.0, faktor=1.5)],
        jahresstueckzahl=5000,
    )
    vorprodukt = 10 * 2 + 3
    assembly_direct = 2 * 1.5
    basis = vorprodukt + assembly_direct
    endpreis = round(basis * 1.15, 2)
    assert result.vorprodukt_gesamt == pytest.approx(vorprodukt)
    assert result.assembly_direkt_gesamt == pytest.approx(assembly_direct)
    assert result.kostenbasis_nach_assembly == pytest.approx(basis)
    assert result.baugruppenpreis_je_stueck == pytest.approx(endpreis)
    assert result.jahresumsatz == pytest.approx(endpreis * 5000)


def test_assembly_ausschuss_auf_vorprodukte():
    """Montageausschuss wirkt auf Einzelteile, Kaufteile und Montagekosten."""
    einzel = _einzelteil(1, 100.0)
    kauf = _kaufteil(1, 20.0, reihenfolge=2)
    montage = _veredelung(1, 10.0, ausschussquote_pct=1.5, reihenfolge=3)
    result = _calc([einzel], [kauf], [montage])

    vorprodukt = 120.0
    direct = 10.0
    basis, surcharge, _ = apply_process_yield(
        __import__("decimal").Decimal(str(vorprodukt)),
        __import__("decimal").Decimal(str(direct)),
        1.5,
    )
    expected_basis = float(basis)
    expected_end = expected_basis * 1.15

    expected_end = round(expected_basis * 1.15, 2)

    assert result.vorprodukt_gesamt == pytest.approx(vorprodukt)
    assert result.assembly_direkt_gesamt == pytest.approx(direct)
    assert result.assembly_ausschuss_zuschlag == pytest.approx(float(surcharge), abs=0.01)
    assert result.kostenbasis_nach_assembly == pytest.approx(expected_basis, abs=0.01)
    assert result.baugruppenpreis_je_stueck == pytest.approx(expected_end, abs=0.01)
    assert result.gewinn_betrag == pytest.approx(round(expected_basis * 0.15, 2), abs=0.01)


def test_fehlender_gewinnsatz():
    with pytest.raises(BaugruppeMarkupError, match="Gewinnsatz"):
        berechne_baugruppe([_einzelteil(1, 1.0)], [], [], gewinn_pct=None)


def test_preis_snapshots_bleiben_berechnungsbasis():
    result = _calc([_einzelteil(1, 7.77)], [], [])
    assert result.einzelteile[0].einzelpreis == pytest.approx(7.77)


def test_ungueltige_menge():
    with pytest.raises(BaugruppeValidationError, match="Menge"):
        _calc([_einzelteil(1, 5.0, menge=0)], [], [])


def test_ungueltiger_mengenfaktor():
    with pytest.raises(BaugruppeValidationError, match="Mengenfaktor"):
        _calc([], [], [_veredelung(1, 1.0, faktor=0)])


def test_doppeltes_einzelteil():
    with pytest.raises(BaugruppeValidationError, match="doppelt"):
        _calc([_einzelteil(1, 1.0), _einzelteil(1, 2.0, reihenfolge=2)], [], [])

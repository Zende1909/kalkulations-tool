"""Unit-Tests für Baugruppenkalkulation."""

from decimal import Decimal

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
FGK_PCT = 22.0
SGA_PCT = 10.0


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


def _kaufteil(
    kid: int,
    einkauf: float,
    menge: float = 1.0,
    *,
    mgk_pct: float = 3.0,
    oem_pct: float = 0.0,
    sga_pct: float = SGA_PCT,
    nominierung: str = "selbstnominiert",
    **kw,
) -> KaufteilEingabe:
    e = Decimal(str(einkauf))
    mgk = e * Decimal(str(mgk_pct)) / Decimal("100")
    oem = e * Decimal(str(oem_pct)) / Decimal("100") if nominierung == "oem_nominiert" else Decimal("0")
    sga_basis = e + mgk + oem
    sga = sga_basis * Decimal(str(sga_pct)) / Decimal("100")
    total = sga_basis + sga
    base = dict(
        kaufteil_id=kid,
        bezeichnung=f"Kaufteil {kid}",
        lieferant="Lieferant A",
        menge=menge,
        reihenfolge=kid,
        nominierung=nominierung,
        einkaufspreis_je_stueck=float(e),
        mgk_satz_pct=mgk_pct,
        mgk_je_stueck=float(mgk),
        oem_handling_satz_pct=oem_pct,
        oem_handling_je_stueck=float(oem),
        sga_satz_pct=sga_pct,
        sga_quelle="standard",
        sga_je_stueck=float(sga),
        kosten_inkl_overheads_je_stueck=float(total),
    )
    base.update(kw)
    return KaufteilEingabe(**base)


def _veredelung(
    vid: int,
    *,
    lohn: float = 0.0,
    maschine: float = 0.0,
    verbrauch: float = 0.0,
    faktor: float = 1.0,
    ausschussquote_pct: float = 0.0,
    **kw,
) -> VeredelungEingabe:
    direkt = lohn + maschine + verbrauch
    base = dict(
        veredelungsschritt_id=vid,
        bezeichnung=f"Montage {vid}",
        reihenfolge=vid,
        mengenfaktor=faktor,
        ausschussquote_pct=ausschussquote_pct,
        lohnkosten_je_stueck=lohn,
        maschinenkosten_je_stueck=maschine,
        verbrauchskosten_je_stueck=verbrauch,
        direktkosten_je_stueck=direkt,
    )
    base.update(kw)
    return VeredelungEingabe(**base)


def _calc(*args, **kwargs):
    kwargs.setdefault("gewinn_pct", GEWINN_PCT)
    kwargs.setdefault("fgk_pct", FGK_PCT)
    return berechne_baugruppe(*args, **kwargs)


def test_ohne_positionen():
    result = _calc([], [], [], jahresstueckzahl=1000)
    assert result.baugruppenpreis_je_stueck == 0.0
    assert result.jahresumsatz == 0.0


def test_mit_einem_einzelteil():
    result = _calc([_einzelteil(1, 5.50, menge=2)], [], [])
    assert result.einzelteile_gesamt == pytest.approx(11.0)
    assert result.vorprodukt_gesamt == pytest.approx(11.0)
    assert result.baugruppenpreis_je_stueck == pytest.approx(11.0 * 1.15, rel=1e-6)


def test_kaufteil_mit_mgk_und_sga():
    kt = _kaufteil(1, 0.10, menge=5, mgk_pct=3.0, sga_pct=10.0)
    result = _calc([], [kt], [])
    assert result.kaufteile_einkauf_gesamt == pytest.approx(0.5)
    assert result.kaufteile_mgk_gesamt == pytest.approx(0.015)
    assert result.kaufteile_sga_gesamt == pytest.approx(0.0515)
    assert result.kaufteile_gesamt == pytest.approx(0.5665)


def test_oem_kaufteil_mit_handling():
    kt = _kaufteil(1, 1.0, mgk_pct=5.0, oem_pct=6.0, nominierung="oem_nominiert")
    result = _calc([], [kt], [])
    assert result.kaufteile_mgk_gesamt == pytest.approx(0.05)
    assert result.kaufteile_oem_handling_gesamt == pytest.approx(0.06)


def test_montage_fgk_auf_direkte_kosten():
    lohn = 500 / 3600 * 12
    maschine = 500 / 3600 * 1.69
    direct = lohn + maschine
    fgk = direct * 0.22
    result = _calc(
        [_einzelteil(1, 19.39)],
        [_kaufteil(1, 0.10, menge=5)],
        [_veredelung(1, lohn=lohn, maschine=maschine)],
    )
    assert result.assembly_direkt_gesamt == pytest.approx(direct, rel=1e-6)
    assert result.assembly_fgk_betrag == pytest.approx(fgk, rel=1e-6)
    assert result.assembly_fgk_satz_pct == 22.0


def test_bumper_endpreis_regression():
    """Bumper-/TSV-Fall: Einzelteil 19,39 + Kaufteil 0,10×5 + Montage + FGK + 1,5% + 15% Gewinn."""
    lohn = 500 / 3600 * 12
    maschine = 500 / 3600 * 1.69
    direct = lohn + maschine
    fgk = direct * 0.22

    einkauf = Decimal("0.10") * Decimal("5")
    mgk = einkauf * Decimal("0.03")
    sga_basis = einkauf + mgk
    sga = sga_basis * Decimal("0.10")
    kaufteil_total = sga_basis + sga
    vorprodukt = Decimal("19.39") + kaufteil_total
    basis_vor = vorprodukt + Decimal(str(direct)) + Decimal(str(fgk))
    basis_nach, _, _ = apply_process_yield(vorprodukt + Decimal(str(fgk)), Decimal(str(direct)), 1.5)
    gewinn = basis_nach * Decimal("0.15")
    expected_end = basis_nach + gewinn

    result = _calc(
        [_einzelteil(1, 19.39)],
        [_kaufteil(1, 0.10, menge=5, mgk_pct=3.0, sga_pct=10.0)],
        [_veredelung(1, lohn=lohn, maschine=maschine, ausschussquote_pct=1.5)],
    )
    assert result.kostenbasis_nach_assembly == pytest.approx(float(basis_nach), rel=1e-6)
    assert result.baugruppenpreis_je_stueck == pytest.approx(float(expected_end), rel=1e-6)


def test_assembly_ausschuss_auf_vorprodukte_und_fgk():
    einzel = _einzelteil(1, 100.0)
    kauf = _kaufteil(1, 20.0, reihenfolge=2)
    lohn = 10.0
    montage = _veredelung(1, lohn=lohn, ausschussquote_pct=1.5, reihenfolge=3)
    result = _calc([einzel], [kauf], [montage])

    fgk = lohn * 0.22
    vorprodukt = 100.0 + float(Decimal("20") * (Decimal("1") + Decimal("0.03")) * (Decimal("1") + Decimal("0.10")))
    basis_nach, surcharge, _ = apply_process_yield(
        Decimal(str(vorprodukt + fgk)),
        Decimal(str(lohn)),
        1.5,
    )
    expected_end = float(basis_nach * Decimal("1.15"))

    assert result.assembly_fgk_betrag == pytest.approx(fgk, rel=1e-6)
    assert result.kostenbasis_nach_assembly == pytest.approx(float(basis_nach), rel=1e-6)
    assert result.baugruppenpreis_je_stueck == pytest.approx(expected_end, rel=1e-6)


def test_fehlender_gewinnsatz():
    with pytest.raises(BaugruppeMarkupError, match="Gewinnsatz"):
        berechne_baugruppe([_einzelteil(1, 1.0)], [], [], gewinn_pct=None, fgk_pct=FGK_PCT)


def test_fehlender_fgk_satz():
    with pytest.raises(BaugruppeMarkupError, match="FGK"):
        berechne_baugruppe([_einzelteil(1, 1.0)], [], [], gewinn_pct=GEWINN_PCT, fgk_pct=None)


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
    assert result.baugruppenpreis_je_stueck == pytest.approx(10.0 * 1.15, rel=1e-6)


def test_ungueltige_menge():
    with pytest.raises(BaugruppeValidationError, match="Menge"):
        _calc([_einzelteil(1, 5.0, menge=0)], [], [])

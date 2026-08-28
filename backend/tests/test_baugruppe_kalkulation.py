"""Unit-Tests für Baugruppenkalkulation."""

from decimal import Decimal

import pytest

from app.services.assembly_calculation import MarkupRates, PositionCalcInput, calculate_assembly
from app.services.baugruppe_kalkulation import (
    BaugruppeMarkupError,
    BaugruppeValidationError,
    EinzelteilEingabe,
    InvestitionAnzeige,
    KaufteilEingabe,
    VeredelungEingabe,
    berechne_baugruppe,
)

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


def _bumper_soll_endpreis_unabhaengig() -> Decimal:
    """Unabhängige Sollrechnung – Formel separat, nicht aus dem Ergebnisobjekt."""
    einzelteil = Decimal("19.39")
    einkauf = Decimal("0.10") * Decimal("5")
    mgk = einkauf * Decimal("3") / Decimal("100")
    kaufteil_vor_sga = einkauf + mgk
    kaufteil_sga = kaufteil_vor_sga * Decimal("10") / Decimal("100")
    vorprodukt = einzelteil + kaufteil_vor_sga + kaufteil_sga

    takt_s = Decimal("500")
    lohn = takt_s / Decimal("3600") * Decimal("12")
    maschine = takt_s / Decimal("3600") * Decimal("1.69")
    direct = lohn + maschine
    fgk = direct * Decimal("22") / Decimal("100")

    basis_vor_ausschuss = vorprodukt + direct + fgk
    basis_nach_ausschuss = basis_vor_ausschuss / (
        Decimal("1") - Decimal("1.5") / Decimal("100")
    )
    return basis_nach_ausschuss * (Decimal("1") + Decimal("15") / Decimal("100"))


def test_bumper_endpreis_regression():
    """Bumper-/TSV-Fall: Einzelteil 19,39 + Kaufteil 0,10×5 + Montage + FGK + 1,5% + 15% Gewinn."""
    lohn = 500 / 3600 * 12
    maschine = 500 / 3600 * 1.69
    direct = lohn + maschine
    fgk = direct * 0.22
    expected_end = float(_bumper_soll_endpreis_unabhaengig())

    result = _calc(
        [_einzelteil(1, 19.39)],
        [_kaufteil(1, 0.10, menge=5, mgk_pct=3.0, sga_pct=10.0)],
        [_veredelung(1, lohn=lohn, maschine=maschine, ausschussquote_pct=1.5)],
    )
    assert result.kaufteile_gesamt == pytest.approx(0.5665)
    assert result.assembly_direkt_gesamt == pytest.approx(direct, rel=1e-6)
    assert result.assembly_fgk_betrag == pytest.approx(fgk, rel=1e-6)
    assert result.kostenbasis_vor_ausschuss == pytest.approx(
        float(Decimal("19.9565") + Decimal(str(direct)) + Decimal(str(fgk))), rel=1e-6
    )
    assert result.baugruppenpreis_je_stueck == pytest.approx(expected_end, rel=1e-6)
    assert result.baugruppenpreis_je_stueck == pytest.approx(26.01, abs=0.01)


def test_bumper_legacy_und_phase_c_parity():
    """Legacy-Berechnen und Phase-C-Recalc liefern denselben ungerundeten Endwert."""
    lohn = 500 / 3600 * 12
    maschine = 500 / 3600 * 1.69
    direct = lohn + maschine
    per_piece_kt = float(Decimal("0.5665") / Decimal("5"))
    expected_end = float(_bumper_soll_endpreis_unabhaengig())

    legacy = _calc(
        [_einzelteil(1, 19.39)],
        [_kaufteil(1, 0.10, menge=5, mgk_pct=3.0, sga_pct=10.0)],
        [_veredelung(1, lohn=lohn, maschine=maschine, ausschussquote_pct=1.5)],
    )
    phase_c = calculate_assembly(
        assembly_type="TOP_LEVEL",
        positions=[
            PositionCalcInput(
                position_id=1,
                position_type="PART",
                sequence=1,
                quantity=1,
                quantity_factor=1,
                price_basis="COST",
                active=True,
                label="Einzelteil",
                name_snapshot="Einzelteil",
                cost_snapshot=19.39,
                price_snapshot=None,
            ),
            PositionCalcInput(
                position_id=2,
                position_type="PURCHASED_PART",
                sequence=2,
                quantity=5,
                quantity_factor=1,
                price_basis=None,
                active=True,
                label="Kaufteil",
                name_snapshot="Kaufteil",
                cost_snapshot=0.10,
                price_snapshot=per_piece_kt,
            ),
            PositionCalcInput(
                position_id=3,
                position_type="PROCESS",
                sequence=3,
                quantity=1,
                quantity_factor=1,
                price_basis=None,
                active=True,
                label="Montage",
                name_snapshot="Montage",
                cost_snapshot=direct,
                price_snapshot=None,
                cost_before_scrap=direct,
                ausschussquote_pct=1.5,
            ),
        ],
        markup_rates=MarkupRates(
            fgk_pct=FGK_PCT,
            vvgk_pct=10.0,
            gewinn_pct=GEWINN_PCT,
            skonto_pct=0.0,
        ),
    )
    assert phase_c.vvgk == pytest.approx(0.0)
    assert legacy.baugruppenpreis_je_stueck == pytest.approx(expected_end, rel=1e-6)
    assert phase_c.endpreis_je_stueck == pytest.approx(expected_end, rel=1e-6)
    assert legacy.baugruppenpreis_je_stueck == pytest.approx(phase_c.endpreis_je_stueck, rel=1e-9)


def test_assembly_ausschuss_auf_vorprodukte_und_fgk():
    einzel = _einzelteil(1, 100.0)
    kauf = _kaufteil(1, 20.0, reihenfolge=2)
    lohn = 10.0
    montage = _veredelung(1, lohn=lohn, ausschussquote_pct=1.5, reihenfolge=3)
    result = _calc([einzel], [kauf], [montage])

    fgk = lohn * 0.22
    vorprodukt = 100.0 + float(Decimal("20") * (Decimal("1") + Decimal("0.03")) * (Decimal("1") + Decimal("0.10")))
    basis_vor = Decimal(str(vorprodukt + fgk + lohn))
    basis_nach = basis_vor / (Decimal("1") - Decimal("1.5") / Decimal("100"))
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

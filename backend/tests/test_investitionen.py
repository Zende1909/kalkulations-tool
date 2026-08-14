"""Tests für Business-Case-Investitionsplanung."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.services.business_case import (
    BaugruppeSnapshot,
    CalcSnapshot,
    InvestitionSnapshot,
    build_business_case,
)
from app.services.investition_service import (
    EINMALZAHLUNG_HINWEIS,
    compute_cost_per_piece,
    validate_amortization_volume,
    validate_investition_input,
)

client = TestClient(app)


def _inv(**kw) -> InvestitionSnapshot:
    base = dict(
        id=1,
        name="Werkzeug Gehäuse",
        investment_type="Werkzeug",
        payment_type="Amortisation",
        amount=200_000.0,
        amortization_volume=20_000,
        cost_per_piece=10.0,
        project_id="Projekt Alpha",
        customer="OEM A",
        calculation_id=5,
        baugruppe_id=None,
        included_in_unit_price=True,
        archived=False,
    )
    base.update(kw)
    return InvestitionSnapshot(**base)


def _calc(**kw) -> CalcSnapshot:
    base = dict(
        id=5,
        teilenummer="GH-001",
        teilebezeichnung="Gehäuse",
        kunde="OEM A",
        projekt="Projekt Alpha",
        jahresstueckzahl=50_000,
        ergebnis={"endpreis_je_stueck": 12.50},
    )
    base.update(kw)
    return CalcSnapshot(**base)


def test_projekt_mit_teilepreis_und_einmalinvestition():
    rows = [
        _inv(payment_type="Einmalzahlung", amount=50_000, cost_per_piece=None, amortization_volume=None, included_in_unit_price=False),
        _inv(),
    ]
    result = build_business_case(
        rows,
        project="Projekt Alpha",
        calc=_calc(),
        calculation_id=5,
    )
    assert result["teilepreis_je_stueck"] == 12.50
    assert result["einmalinvestitionen_gesamt"] == 50_000.0
    assert result["investitionen_gesamt"] == 250_000.0
    assert result["preis_inkl_amortisation_je_stueck"] == 22.50


def test_projekt_mit_amortisierter_investition():
    result = build_business_case(
        [_inv()],
        project="Projekt Alpha",
        calc=_calc(),
        calculation_id=5,
    )
    assert result["amortisationsinvestitionen_gesamt"] == 200_000.0
    assert result["amortisationsanteil_je_stueck"] == 10.0


def test_amortisation_20000_ok():
    assert validate_amortization_volume(20_000) == 20_000


def test_amortisation_0_abgelehnt():
    with pytest.raises(HTTPException) as exc:
        validate_amortization_volume(0)
    assert exc.value.status_code == 422


def test_amortisation_dezimal_abgelehnt():
    with pytest.raises(HTTPException) as exc:
        validate_amortization_volume(20_000.0001)
    assert exc.value.status_code == 422


def test_einmalzahlung_ohne_amortisationsvolumen():
    result = validate_investition_input(
        name="Lehre",
        investment_type="Lehre",
        payment_type="Einmalzahlung",
        amount=5000.0,
        amortization_volume=None,
        project="Projekt Alpha",
    )
    assert result["amortization_volume"] is None


def test_einmalzahlung_nicht_im_teilepreis():
    rows = [
        _inv(
            payment_type="Einmalzahlung",
            amount=50_000,
            cost_per_piece=None,
            amortization_volume=None,
            included_in_unit_price=False,
        )
    ]
    result = build_business_case(rows, project="Projekt Alpha", calc=_calc(), calculation_id=5)
    assert result["preis_inkl_amortisation_je_stueck"] == 12.50
    assert result["amortisationsanteil_je_stueck"] == 0.0


def test_amortisationsanteil_im_teilepreis():
    assert compute_cost_per_piece(200_000, "Amortisation", 20_000) == 10.0
    result = build_business_case([_inv()], calc=_calc(), calculation_id=5)
    assert result["preis_inkl_amortisation_je_stueck"] == 22.50


def test_filter_standardmaessig_alle():
    response = client.get("/api/v1/investitionen/business-case")
    assert response.status_code == 401


def test_business_case_ohne_investitionen():
    result = build_business_case([], project="Leer")
    assert result["anzahl_investitionen"] == 0
    assert result["investitionen_gesamt"] == 0


def test_business_case_mehrere_investitionen():
    rows = [
        _inv(id=1, amount=100_000, cost_per_piece=5.0),
        _inv(id=2, name="Vorrichtung", investment_type="Vorrichtung", amount=30_000, cost_per_piece=3.0),
        _inv(
            id=3,
            name="Einmal Werkzeug",
            payment_type="Einmalzahlung",
            amount=20_000,
            cost_per_piece=None,
            amortization_volume=None,
            included_in_unit_price=False,
        ),
    ]
    result = build_business_case(rows, project="Projekt Alpha", calc=_calc(), calculation_id=5)
    assert result["anzahl_investitionen"] == 3
    assert result["investitionen_gesamt"] == 150_000.0
    assert result["amortisationsanteil_je_stueck"] == 8.0


def test_investition_einzelteil_zuordnen():
    result = validate_investition_input(
        name="Werkzeug",
        investment_type="Werkzeug",
        payment_type="Amortisation",
        amount=40_000,
        amortization_volume=20_000,
        project="Projekt Alpha",
        calculation_id=5,
    )
    assert result["included_in_unit_price"] is True


def test_investition_baugruppe_zuordnen():
    result = validate_investition_input(
        name="Montageanlage",
        investment_type="Montageanlage",
        payment_type="Amortisation",
        amount=80_000,
        amortization_volume=4_000,
        project="Projekt Alpha",
        baugruppe_id=3,
    )
    assert result["included_in_unit_price"] is True
    bg = BaugruppeSnapshot(
        id=3,
        name="Front",
        teilenummer="FS-1",
        kunde="OEM",
        projekt="Projekt Alpha",
        jahresstueckzahl=10_000,
        ergebnis={"baugruppenpreis_je_stueck": 25.0, "jahresumsatz": 250_000},
    )
    inv = _inv(baugruppe_id=3, calculation_id=None, cost_per_piece=20.0, amount=80_000, amortization_volume=4_000)
    bc = build_business_case([inv], project="Projekt Alpha", baugruppe=bg, baugruppe_id=3)
    assert bc["baugruppenpreis_je_stueck"] == 25.0
    assert bc["preis_inkl_amortisation_je_stueck"] == 45.0


def test_einmalzahlung_hinweis():
    assert "Stückpreis" in EINMALZAHLUNG_HINWEIS

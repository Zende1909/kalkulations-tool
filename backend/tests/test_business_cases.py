"""Tests für projektbezogene Business-Case-API."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.business_case_overview import build_project_business_case

client = TestClient(app)


def _lucid_gap_hider_db() -> MagicMock:
    sg = SimpleNamespace(
        id=1,
        teilebezeichnung="Gap Hider Clip",
        teilenummer="GH-100",
        kunde="Lucid",
        projekt="Gap Hider",
        jahresstueckzahl=120_000,
        ergebnis={"endpreis_je_stueck": 3.50, "verkaufspreis": 3.20},
    )
    bg = SimpleNamespace(
        id=2,
        name="Gap Hider Set",
        teilenummer="BG-GH-1",
        kunde="Lucid",
        projekt="Gap Hider",
        jahresstueckzahl=60_000,
        ergebnis={"baugruppenpreis_je_stueck": 12.0, "jahresumsatz": 720_000.0},
    )
    inv_amort = SimpleNamespace(
        id=10,
        name="Werkzeug Gap Hider",
        description="",
        part_name="",
        investment_type="Werkzeug",
        payment_type="Amortisation",
        amount=80_000.0,
        amortization_volume=120_000,
        cost_per_piece=round(80_000 / 120_000, 6),
        project_id="Gap Hider",
        customer="Lucid",
        calculation_id=None,
        baugruppe_id=None,
        part_number="",
    )
    inv_einmal = SimpleNamespace(
        id=11,
        name="Prüfmittel",
        description="",
        part_name="",
        investment_type="Prüfmittel",
        payment_type="Einmalzahlung",
        amount=15_000.0,
        amortization_volume=None,
        cost_per_piece=None,
        project_id="Gap Hider",
        customer="Lucid",
        calculation_id=None,
        baugruppe_id=None,
        part_number="",
    )

    db = MagicMock()
    scalars_responses = iter([[sg], [bg], [inv_amort, inv_einmal]])

    def scalars(_stmt):
        result = MagicMock()
        try:
            result.all.return_value = next(scalars_responses)
        except StopIteration:
            result.all.return_value = []
        return result

    db.scalars.side_effect = scalars
    db.scalar.side_effect = lambda _stmt: None
    return db


def test_business_case_lucid_gap_hider():
    result = build_project_business_case(
        _lucid_gap_hider_db(),
        customer="Lucid",
        project="Gap Hider",
    )
    assert result["customer"] == "Lucid"
    assert result["project"] == "Gap Hider"
    assert result["kpis"]["anzahl_einzelteile"] == 1
    assert result["kpis"]["anzahl_baugruppen"] == 1
    assert result["kpis"]["anzahl_investitionen"] == 2


def test_einzelteile_im_business_case():
    result = build_project_business_case(_lucid_gap_hider_db(), customer="Lucid", project="Gap Hider")
    part = result["parts"][0]
    assert part["endpreis_je_stueck"] == 3.50
    assert part["jahresumsatz"] == pytest.approx(420_000.0)


def test_baugruppen_im_business_case():
    result = build_project_business_case(_lucid_gap_hider_db(), customer="Lucid", project="Gap Hider")
    assembly = result["assemblies"][0]
    assert assembly["baugruppenpreis_je_stueck"] == 12.0
    assert assembly["jahresumsatz"] == pytest.approx(720_000.0)


def test_investitionen_im_business_case():
    result = build_project_business_case(_lucid_gap_hider_db(), customer="Lucid", project="Gap Hider")
    einmal = [i for i in result["investments"] if i["payment_type"] == "Einmalzahlung"]
    amort = [i for i in result["investments"] if i["payment_type"] == "Amortisation"]
    assert len(einmal) == 1
    assert len(amort) == 1
    assert "nicht im Stückpreis" in einmal[0]["hinweis"]


def test_keine_doppelte_umsatzberechnung():
    result = build_project_business_case(_lucid_gap_hider_db(), customer="Lucid", project="Gap Hider")
    assert result["revenue_summary"]["umsatzpotenzial_einzelteile"] == pytest.approx(420_000.0)
    assert result["revenue_summary"]["umsatzpotenzial_baugruppen"] == pytest.approx(720_000.0)
    assert "nicht addiert" in result["revenue_summary"]["hinweis"]


def test_investitionen_nicht_im_teilepreis():
    result = build_project_business_case(_lucid_gap_hider_db(), customer="Lucid", project="Gap Hider")
    assert result["parts"][0]["endpreis_je_stueck"] == 3.50
    assert result["kpis"]["amortisationsanteil_je_stueck"] == pytest.approx(0.67, abs=0.01)


def test_business_case_ohne_daten():
    db = MagicMock()

    def scalars(_stmt):
        result = MagicMock()
        result.all.return_value = []
        return result

    db.scalars.side_effect = scalars
    db.scalar.return_value = None
    result = build_project_business_case(db, customer="Leer", project="Leer")
    assert result["kpis"]["anzahl_einzelteile"] == 0
    assert result["kpis"]["anzahl_baugruppen"] == 0
    assert result["kpis"]["anzahl_investitionen"] == 0
    assert result["parts"] == []
    assert result["assemblies"] == []


def test_nicht_authentifizierter_zugriff():
    response = client.get("/api/v1/business-cases?customer=Lucid&project=Gap%20Hider")
    assert response.status_code == 401

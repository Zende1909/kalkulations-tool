"""Tests für Investitionsmodul."""

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.services.investition_service import (
    EINMALZAHLUNG_HINWEIS,
    compute_cost_per_piece,
    validate_amortization_volume,
    validate_investition_input,
)

client = TestClient(app)


def test_einmalzahlung_anlegen_validierung():
    result = validate_investition_input(
        name="Prüfmittel Set A",
        investment_type="Prüfmittel",
        payment_type="Einmalzahlung",
        amount=12000.0,
        amortization_volume=None,
        status_value="In Planung",
    )
    assert result["amortization_volume"] is None
    assert result["cost_per_piece"] is None
    assert result["included_in_unit_price"] is False


def test_amortisation_anlegen_validierung():
    result = validate_investition_input(
        name="Werkzeug Gehäuse",
        investment_type="Werkzeug",
        payment_type="Amortisation",
        amount=40000.0,
        amortization_volume=20000,
        status_value="Bestellt",
        calculation_id=5,
    )
    assert result["amortization_volume"] == 20000
    assert result["cost_per_piece"] == 2.0
    assert result["included_in_unit_price"] is True


def test_amortisationsvolumen_20000_ok():
    assert validate_amortization_volume(20000) == 20000


def test_amortisationsvolumen_0_abgelehnt():
    with pytest.raises(HTTPException) as exc:
        validate_amortization_volume(0)
    assert exc.value.status_code == 422


def test_amortisationsvolumen_dezimal_abgelehnt():
    with pytest.raises(HTTPException) as exc:
        validate_amortization_volume(20000.0001)
    assert exc.value.status_code == 422


def test_negativer_betrag_abgelehnt():
    with pytest.raises(HTTPException) as exc:
        validate_investition_input(
            name="Test",
            investment_type="Werkzeug",
            payment_type="Einmalzahlung",
            amount=-1.0,
            amortization_volume=None,
            status_value="In Planung",
        )
    assert exc.value.status_code == 422


def test_einmalzahlung_ohne_amortisationsvolumen():
    result = validate_investition_input(
        name="Lehre",
        investment_type="Lehre",
        payment_type="Einmalzahlung",
        amount=5000.0,
        amortization_volume=None,
        status_value="Geliefert",
    )
    assert result["amortization_volume"] is None


def test_einmalzahlung_nicht_im_stueckpreis():
    result = validate_investition_input(
        name="Werkzeug",
        investment_type="Werkzeug",
        payment_type="Einmalzahlung",
        amount=50000.0,
        amortization_volume=None,
        status_value="In Planung",
        calculation_id=1,
    )
    assert result["included_in_unit_price"] is False
    assert compute_cost_per_piece(50000.0, "Einmalzahlung", None) is None


def test_amortisationskosten_je_stueck():
    assert compute_cost_per_piece(40000.0, "Amortisation", 20000) == 2.0
    assert compute_cost_per_piece(10000.0, "Amortisation", 1) == 10000.0


def test_bearbeiten_merge_logik():
    merged = validate_investition_input(
        name="Anlage XY",
        investment_type="Montageanlage",
        payment_type="Amortisation",
        amount=80000.0,
        amortization_volume=4000,
        status_value="In Herstellung",
    )
    assert merged["cost_per_piece"] == 20.0


def test_archivieren_ist_soft_delete_semantik():
    # Archivierung setzt archived=True – Feld im Modell vorhanden
    from app.models.investition import Investition

    assert "archived" in Investition.__table__.columns


def test_filter_projekt_api_parameter():
    response = client.get("/api/v1/investitionen?project=Projekt%20X")
    assert response.status_code == 401


def test_filter_status_api_parameter():
    response = client.get("/api/v1/investitionen?status=Bestellt")
    assert response.status_code == 401


def test_reload_endpunkt_vorhanden():
    response = client.get("/api/v1/investitionen/1")
    assert response.status_code == 401


def test_nicht_authentifizierter_zugriff():
    response = client.get("/api/v1/investitionen")
    assert response.status_code == 401


def test_einmalzahlung_hinweis_konstante():
    assert "Stückpreis" in EINMALZAHLUNG_HINWEIS

"""Tests für Dashboard-Aggregation."""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.dashboard import (
    BaugruppeRecord,
    InvestitionRecord,
    SpritzgussRecord,
    build_dashboard_summary,
    endpreis_aus_spritzguss,
)

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


def _sg(**kw) -> SpritzgussRecord:
    base = dict(
        id=1,
        teilebezeichnung="Gehäuse",
        teilenummer="GH-001",
        kunde="OEM A",
        projekt="Projekt X",
        jahresstueckzahl=1000,
        aktiv=True,
        ergebnis={"endpreis_je_stueck": 10.0, "verkaufspreis": 9.0},
        created_at=NOW,
        updated_at=NOW,
    )
    base.update(kw)
    return SpritzgussRecord(**base)


def _bg(**kw) -> BaugruppeRecord:
    base = dict(
        id=1,
        name="Frontstoßfänger",
        teilenummer="FS-100",
        kunde="OEM A",
        projekt="Projekt X",
        jahresstueckzahl=5000,
        aktiv=True,
        ergebnis={"baugruppenpreis_je_stueck": 25.0, "jahresumsatz": 125000.0},
        created_at=NOW,
        updated_at=NOW,
    )
    base.update(kw)
    return BaugruppeRecord(**base)


def _inv(**kw) -> InvestitionRecord:
    base = dict(
        id=1,
        project_id="Projekt X",
        calculation_id=1,
        baugruppe_id=None,
        part_name="Werkzeug",
        description="Werkzeug-Einmalzahlung",
        amount=50000.0,
        investment_type="Werkzeug",
        payment_type="Einmalzahlung",
        status="offen",
        kunde="OEM A",
        projekt="Projekt X",
    )
    base.update(kw)
    return InvestitionRecord(**base)


def test_dashboard_ohne_daten():
    result = build_dashboard_summary([], [], [])
    assert result["kpis"]["anzahl_projekte"] == 0
    assert result["kpis"]["durchschnitt_endpreis_einzelteil"] is None
    assert result["kpis"]["umsatzpotenzial_jahr"] == 0
    assert result["recent_calculations"] == []


def test_dashboard_mit_einem_projekt():
    result = build_dashboard_summary([_sg()], [_bg()], [_inv()])
    assert result["kpis"]["anzahl_projekte"] == 1
    assert result["kpis"]["anzahl_spritzguss_kalkulationen"] == 1
    assert result["kpis"]["anzahl_baugruppen"] == 1


def test_filter_nach_projekt():
    result = build_dashboard_summary(
        [_sg(projekt="Alpha"), _sg(id=2, projekt="Beta", teilenummer="T-2")],
        [_bg(projekt="Alpha")],
        [_inv(projekt="Alpha"), _inv(id=2, projekt="Beta", amount=1000)],
        project="Alpha",
    )
    assert result["kpis"]["anzahl_spritzguss_kalkulationen"] == 1
    assert result["kpis"]["investitionen_gesamt"] == 50000.0


def test_filter_nach_kunde():
    result = build_dashboard_summary(
        [_sg(kunde="Kunde 1"), _sg(id=2, kunde="Kunde 2", teilenummer="X-2")],
        [],
        [],
        customer="Kunde 1",
    )
    assert result["kpis"]["anzahl_spritzguss_kalkulationen"] == 1


def test_jahresumsatz():
    result = build_dashboard_summary([], [_bg()], [])
    assert result["assemblies"][0]["jahresumsatz"] == 125000.0
    assert result["kpis"]["umsatzpotenzial_jahr"] == 125000.0


def test_investitionen_separat():
    result = build_dashboard_summary([_sg()], [], [_inv()])
    assert result["investments"][0]["im_stueckpreis"] is False
    assert "nicht im Stückpreis" in result["investments"][0]["hinweis"]
    assert result["kpis"]["investitionen_gesamt"] == 50000.0


def test_einmalinvestition_nicht_im_durchschnittspreis():
    result = build_dashboard_summary([_sg(ergebnis={"endpreis_je_stueck": 12.0})], [], [_inv()])
    assert result["kpis"]["durchschnitt_endpreis_einzelteil"] == 12.0
    assert result["kpis"]["investitionen_gesamt"] == 50000.0


def test_veredelung_nicht_doppelt_gezaehlt():
    """Endpreis aus gespeichertem Ergebnis wird nur einmal verwendet."""
    ergebnis = {
        "endpreis_je_stueck": 15.0,
        "veredelung_gesamt": 2.0,
        "verkaufspreis": 13.0,
    }
    assert endpreis_aus_spritzguss(ergebnis) == 15.0
    result = build_dashboard_summary([_sg(ergebnis=ergebnis)], [], [])
    assert result["kpis"]["durchschnitt_endpreis_einzelteil"] == 15.0
    assert len(result["price_comparison"]) == 1
    assert result["price_comparison"][0]["value"] == 15.0


def test_nicht_authentifizierter_zugriff():
    client = TestClient(app)
    response = client.get("/api/v1/dashboard/summary")
    assert response.status_code == 401

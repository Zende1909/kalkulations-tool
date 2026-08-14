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
    assert result["kpis"]["durchschnitt_preis_pro_stueck"] is None
    assert result["recent_calculations"] == []
    assert result["has_data"] is False
    assert result["empty_message"]
    assert "Filter" in result["empty_message"]
    assert result["cost_structure"]
    assert all(bucket["value"] == 0 for bucket in result["cost_structure"])


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


def test_dashboard_summen_und_jahresumsatz():
    result = build_dashboard_summary(
        [_sg(jahresstueckzahl=1000, ergebnis={"endpreis_je_stueck": 10.0})],
        [_bg(jahresstueckzahl=5000, ergebnis={"baugruppenpreis_je_stueck": 25.0, "jahresumsatz": 125000.0})],
        [_inv(amount=50000.0), _inv(id=2, amount=25000.0, project_id="Projekt X")],
    )
    assert result["kpis"]["umsatzpotenzial_jahr"] == 135000.0
    assert result["kpis"]["investitionen_gesamt"] == 75000.0
    assert result["kpis"]["durchschnitt_preis_pro_stueck"] == 17.5
    assert result["investment_by_project"][0]["betrag"] == 75000.0


def test_dashboard_filter_kunde_und_projekt():
    result = build_dashboard_summary(
        [
            _sg(kunde="OEM A", projekt="Alpha"),
            _sg(id=2, kunde="OEM B", projekt="Beta", teilenummer="T-2"),
        ],
        [_bg(kunde="OEM A", projekt="Alpha"), _bg(id=2, kunde="OEM B", projekt="Beta", teilenummer="B-2")],
        [_inv(kunde="OEM A", projekt="Alpha"), _inv(id=2, kunde="OEM B", projekt="Beta", amount=10)],
        customer="OEM A",
        project="Alpha",
    )
    assert result["kpis"]["anzahl_spritzguss_kalkulationen"] == 1
    assert result["kpis"]["anzahl_baugruppen"] == 1
    assert result["kpis"]["investitionen_gesamt"] == 50000.0
    assert result["has_data"] is True


def test_dashboard_leere_datenmenge_nach_filter():
    result = build_dashboard_summary(
        [_sg()],
        [_bg()],
        [_inv()],
        customer="Unbekannt",
    )
    assert result["has_data"] is False
    assert result["kpis"]["anzahl_baugruppen"] == 0
    assert "anlegen" in (result["empty_message"] or "").lower() or "Filter" in (result["empty_message"] or "")


def test_dashboard_phase_c_endpreis_als_baugruppenpreis():
    result = build_dashboard_summary(
        [],
        [_bg(ergebnis={"endpreis_je_stueck": 13.37, "herstellkosten": 10.57, "skonto": 0})],
        [],
    )
    assert result["assemblies"][0]["preis_je_stueck"] == 13.37
    assert result["kpis"]["durchschnitt_baugruppenpreis"] == 13.37


def test_dashboard_kalkulationsart_filter():
    result = build_dashboard_summary([_sg()], [_bg()], [_inv()], kalkulationsart="Baugruppe")
    assert result["kpis"]["anzahl_spritzguss_kalkulationen"] == 0
    assert result["kpis"]["anzahl_baugruppen"] == 1


def test_dashboard_status_und_zeitraum():
    from datetime import date

    other = _sg(id=2, teilenummer="ALT", updated_at=NOW.replace(year=2020))
    result = build_dashboard_summary(
        [_sg(status="aktiv"), other],
        [_bg(status="entwurf")],
        [],
        status="aktiv",
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
    )
    assert result["kpis"]["anzahl_spritzguss_kalkulationen"] == 1
    assert result["kpis"]["anzahl_baugruppen"] == 0


def test_investitionssummen_je_projekt():
    result = build_dashboard_summary(
        [],
        [],
        [
            _inv(projekt="A", amount=10),
            _inv(id=2, projekt="A", amount=15),
            _inv(id=3, projekt="B", amount=7),
        ],
    )
    by_project = {row["projekt"]: row["betrag"] for row in result["investment_by_project"]}
    assert by_project["A"] == 25.0
    assert by_project["B"] == 7.0
    assert result["recent_investments"]

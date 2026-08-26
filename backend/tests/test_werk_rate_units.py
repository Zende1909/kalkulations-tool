"""Werk-Kapitalkostensätze: UI-% ↔ interner Anteil; OEE bleibt Anteil."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.hierarchy_plant import WerkCreate, WerkUpdate
from app.services.machine_hourly_rate import MachineRateInput, berechne_maschinenstundensatz


def test_werk_create_stores_rate_fractions_not_percent_points():
    """API erwartet Anteile (nach FE /100): 8 % → 0,08."""
    body = WerkCreate(
        land_id=1,
        code="R-FRAC",
        name="Rabigh",
        currency="USD",
        fx_to_eur=0.92,
        oee=0.9,
        zinssatz=0.08,
        versicherungssatz=0.0045,
        instandhaltungssatz=0.02,
    )
    assert body.zinssatz == pytest.approx(0.08)
    assert body.versicherungssatz == pytest.approx(0.0045)
    assert body.instandhaltungssatz == pytest.approx(0.02)
    assert body.oee == pytest.approx(0.9)


def test_werk_create_rejects_percent_points_as_fraction():
    with pytest.raises(ValidationError) as exc:
        WerkCreate(
            land_id=1,
            code="R-BAD",
            name="X",
            currency="USD",
            fx_to_eur=0.92,
            zinssatz=8,  # fälschlich Prozentpunkte statt Anteil
        )
    assert "Zinssatz" in str(exc.value)
    assert "0,08" in str(exc.value) or "0.08" in str(exc.value)


def test_werk_create_rejects_oee_above_one():
    with pytest.raises(ValidationError) as exc:
        WerkCreate(
            land_id=1,
            code="R-OEE",
            name="X",
            currency="USD",
            fx_to_eur=0.92,
            oee=90,
        )
    assert "OEE" in str(exc.value)


def test_werk_update_accepts_german_fraction_strings():
    upd = WerkUpdate(zinssatz="0,08", versicherungssatz="0,0045", oee="0,9")
    assert upd.zinssatz == pytest.approx(0.08)
    assert upd.versicherungssatz == pytest.approx(0.0045)
    assert upd.oee == pytest.approx(0.9)


def test_machine_rate_uses_kaec_fractions():
    """8 % / 0,45 % / 2 % / OEE 90 % als Anteile in der Stundensatzformel."""
    data = MachineRateInput(
        arbeitstage_pro_jahr=254,
        schichten_pro_tag=2,
        stunden_pro_schicht=8,
        oee=0.9,
        investment=347300,
        flaeche_sqm=26.5,
        space_cost_satz_pro_sqm_jahr=30,
        abschreibungsdauer_jahre=10,
        zinssatz=0.08,
        versicherungssatz=0.0045,
        instandhaltungssatz=0.02,
        stromverbrauch_kwh_h=22,
        strompreis=0.06,
        druckluftverbrauch_m3_h=5,
        druckluftpreis=0.06,
        kuehlwasserverbrauch_m3_h=1.8,
        kuehlwasserpreis=0.03,
        fx_to_eur=0.92,
        source_currency="USD",
    )
    r = berechne_maschinenstundensatz(data)
    assert r.zinsen_pro_stunde == pytest.approx(3.7981189851268593, rel=1e-5)
    assert r.versicherung_pro_stunde == pytest.approx(0.42728838582677164, rel=1e-5)
    assert r.instandhaltung_pro_stunde == pytest.approx(1.8990594925634297, rel=1e-5)
    # Energiepreise sind absolute Werte, keine Prozente
    assert r.energie_pro_stunde == pytest.approx(1.674, rel=1e-3)

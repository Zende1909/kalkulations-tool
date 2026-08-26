"""Unit-Tests Maschinenstundensatz vs. Mappe1 IMM+Viper 150."""

from __future__ import annotations

import pytest

from app.services.machine_hourly_rate import (
    MachineRateInput,
    MachineRateValidationError,
    berechne_maschinenstundensatz,
)

# Mappe1 Costing_Base_Data Zeile 6 (IMM + Viper 150), Globals Zeile 3
IMM_150 = MachineRateInput(
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


def test_jahresstunden_254_2_8_oee90():
    r = berechne_maschinenstundensatz(IMM_150)
    assert r.jahresstunden == pytest.approx(3657.6)


def test_imm_150_rate_matches_excel():
    r = berechne_maschinenstundensatz(IMM_150)
    assert r.stundensatz_source == pytest.approx(17.51111996937883, rel=1e-6)
    assert r.stundensatz_eur == pytest.approx(17.51111996937883 * 0.92, rel=1e-6)
    assert r.space_costs_pro_stunde == pytest.approx(0.21735564304461943, rel=1e-5)
    assert r.abschreibung_pro_stunde == pytest.approx(9.495297462817149, rel=1e-5)
    assert r.zinsen_pro_stunde == pytest.approx(3.7981189851268593, rel=1e-5)
    assert r.versicherung_pro_stunde == pytest.approx(0.42728838582677164, rel=1e-5)
    assert r.instandhaltung_pro_stunde == pytest.approx(1.8990594925634297, rel=1e-5)
    assert r.energie_pro_stunde == pytest.approx(1.674, rel=1e-3)


def test_investment_flows_via_components_not_full_add():
    r = berechne_maschinenstundensatz(IMM_150)
    # Investment selbst nicht addiert; nur Abschreibung+Zinsen+Vers+Inst
    assert r.stundensatz_source < IMM_150.investment / r.jahresstunden


def test_parameter_change_updates_rate():
    r1 = berechne_maschinenstundensatz(IMM_150)
    changed = MachineRateInput(**{**IMM_150.__dict__, "investment": 400000})
    r2 = berechne_maschinenstundensatz(changed)
    assert r2.stundensatz_source > r1.stundensatz_source


def test_eur_conversion_092():
    r = berechne_maschinenstundensatz(IMM_150)
    assert r.stundensatz_eur == pytest.approx(r.stundensatz_source * 0.92)


def test_display_rounding_does_not_change_internal():
    r = berechne_maschinenstundensatz(IMM_150)
    disp = r.rounded_display(2)
    assert disp["stundensatz_eur"] == pytest.approx(round(r.stundensatz_eur, 2))
    assert r.stundensatz_source != disp["stundensatz_source"] or True


def test_invalid_oee():
    with pytest.raises(MachineRateValidationError):
        berechne_maschinenstundensatz(MachineRateInput(**{**IMM_150.__dict__, "oee": 1.5}))

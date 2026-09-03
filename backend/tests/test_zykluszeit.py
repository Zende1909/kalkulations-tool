"""Tests für die Zykluszeit-Schätzung (Kühlzeit nach IKET, Nebenzeiten je Klasse)."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.api.v1.spritzguss import _run_zykluszeit_for_model
from app.core.security import UserRole
from app.database import get_db
from app.dependencies import get_current_user
from app.models.material import Material
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.schemas.material import MaterialCreate
from tests.materialgruppen_test_helpers import create_material_tables, seed_materialgruppen
from app.schemas.zykluszeit import ZykluszeitFields
from app.services.export_builders import _zykluszeit_export_rows
from app.services.material_thermik import (
    MATERIALGRUPPEN_DEFAULTS,
    defaults_fuer_gruppe,
    normalisiere_gruppe,
)
from app.services.maschinen_groesse import MaschinenGroesseInput, berechne_maschinen_groesse
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss
from app.services.zykluszeit import (
    DEFAULT_ENTNAHMEART,
    DEFAULT_GROESSENKLASSE,
    ENTNAHME_GREIFER_JE_WEITERE_KAVITAET_S,
    ENTNAHME_GREIFER_KAVITAETEN_MAX_S,
    GROESSENKLASSE_AUTO,
    GROESSENKLASSEN,
    GROSSTEIL_WARNUNG_TEXT,
    KUEHLFAKTOR,
    MAX_WANDSTAERKE_MM,
    PROZESSAUFWAND_ZUSCHLAG_S,
    SPRITZZEIT_MAX_S,
    SPRITZZEIT_MIN_S,
    SPRITZZEIT_OHNE_SCHUSSGEWICHT_S,
    ZykluszeitInput,
    automatische_nebenzeiten,
    berechne_zykluszeit,
    dosierzeit_s,
    einspritz_nachdruckzeit_s,
    entnahmezeit_s,
    klasse_aus_zuhaltekraft,
    massgebliche_zuhaltekraft_t,
    normalisiere_entnahmeart,
    normalisiere_groessenklasse,
    plastifizierleistung_kg_h,
    werkzeugbewegungszeit_s,
)

API = "/api/v1"

# Beispielwerte aus IKET "Zykluszeitbestimmung" (POM, Delrin 500P NC010).
POM = {
    "schmelzdichte_kg_m3": 783.17,
    "waermekapazitaet_j_kg_k": 3000.0,
    "waermeleitfaehigkeit_w_m_k": 0.27,
    "werkzeugtemperatur_c": 40.0,
    "schmelzetemperatur_c": 220.0,
    "entformungstemperatur_c": 80.0,
}
POM_WANDSTAERKE_MM = 4.5
IKET_NEBENZEITEN_S = 12.5


# Automatische Nebenzeit für `_pom_input()` ohne Zuhaltekraft und Schussgewicht:
# 6,0 s Werkzeugbewegung + 3,0 s Einspritzen (Fallback) + 0,0 s Dosierüberhang
# + 5,0 s Greiferentnahme (Fallback) + 0,0 s Prozessaufwand.
POM_AUTO_NEBENZEIT_S = 14.0

# Referenzbeispiel aus der Praxis: PP, 2.414 g Schussgewicht, 1 Kavität,
# 2.653 t erforderliche Zuhaltekraft, kühlzeitrelevante Wandstärke 2,5 mm.
REFERENZ = {
    "wandstaerke_mm": 2.5,
    "materialgruppe": "PP",
    "schussgewicht_g": 2414.0,
    "kavitaeten": 1,
    "zuhaltekraft_t": 2653.0,
}


def _pom_input(**overrides) -> ZykluszeitInput:
    kwargs = {"wandstaerke_mm": POM_WANDSTAERKE_MM, "materialgruppe": "POM"}
    kwargs.update(overrides)
    return ZykluszeitInput(**kwargs)


def _referenz_input(**overrides) -> ZykluszeitInput:
    kwargs = dict(REFERENZ)
    kwargs.update(overrides)
    return ZykluszeitInput(**kwargs)


def _erwartete_kuehlzeit(
    *,
    wandstaerke_mm: float,
    schmelzdichte_kg_m3: float,
    waermekapazitaet_j_kg_k: float,
    waermeleitfaehigkeit_w_m_k: float,
    werkzeugtemperatur_c: float,
    schmelzetemperatur_c: float,
    entformungstemperatur_c: float,
) -> tuple[float, float]:
    """Unabhängige Nachrechnung der IKET-Formel (nicht aus dem Ergebnisobjekt)."""
    alpha = waermeleitfaehigkeit_w_m_k / (schmelzdichte_kg_m3 * waermekapazitaet_j_kg_k)
    quotient = (schmelzetemperatur_c - werkzeugtemperatur_c) / (
        entformungstemperatur_c - werkzeugtemperatur_c
    )
    t_opt = ((wandstaerke_mm / 1000.0) ** 2 / (alpha * math.pi**2)) * math.log(
        (4.0 / math.pi) * quotient
    )
    return alpha, t_opt


# --------------------------------------------------------------------------------------
# Formel und POM-Regression
# --------------------------------------------------------------------------------------


def test_pom_regression_gegen_iket_beispiel():
    """Regressionsfall aus der IKET-Datei; Sollwert unabhängig nachgerechnet."""
    result = berechne_zykluszeit(_pom_input(nebenzeiten_gesamt_s=IKET_NEBENZEITEN_S))
    alpha_soll, t_opt_soll = _erwartete_kuehlzeit(wandstaerke_mm=POM_WANDSTAERKE_MM, **POM)

    assert result.berechenbar is True
    assert result.hinweis is None
    assert result.temperaturleitfaehigkeit_m2_s == pytest.approx(alpha_soll)
    assert result.temperaturleitfaehigkeit_m2_s == pytest.approx(1.149176e-7, rel=1e-6)
    assert result.optimale_kuehlzeit_s == pytest.approx(t_opt_soll)
    assert result.optimale_kuehlzeit_s == pytest.approx(31.17, abs=0.01)
    assert result.kuehlzeit_s == pytest.approx(t_opt_soll * 1.5)
    assert result.nebenzeiten_gesamt_s == pytest.approx(IKET_NEBENZEITEN_S)
    assert result.gesamtzykluszeit_s == pytest.approx(t_opt_soll * 1.5 + IKET_NEBENZEITEN_S)
    assert result.gesamtzykluszeit_s == pytest.approx(59.25, abs=0.01)


def test_kuehlfaktor_ist_fest_bei_1_5():
    assert KUEHLFAKTOR == 1.5
    result = berechne_zykluszeit(_pom_input())
    assert result.kuehlfaktor == pytest.approx(1.5)
    assert result.kuehlzeit_s == pytest.approx(result.optimale_kuehlzeit_s * 1.5)


def test_wandstaerke_geht_quadratisch_ein():
    einfach = berechne_zykluszeit(_pom_input(wandstaerke_mm=2.0))
    doppelt = berechne_zykluszeit(_pom_input(wandstaerke_mm=4.0))
    assert doppelt.optimale_kuehlzeit_s == pytest.approx(einfach.optimale_kuehlzeit_s * 4)


def test_keine_zwischenrundung():
    result = berechne_zykluszeit(_pom_input())
    assert result.gesamtzykluszeit_s == pytest.approx(
        result.kuehlzeit_s + result.nebenzeiten_gesamt_s, rel=0, abs=1e-12
    )
    assert result.gesamtzykluszeit_s != round(result.gesamtzykluszeit_s, 2)


def test_alle_materialgruppen_liefern_plausible_kuehlzeit():
    """Jede Gruppe muss rechenbar sein und im üblichen α-Band liegen."""
    for gruppe in MATERIALGRUPPEN_DEFAULTS:
        result = berechne_zykluszeit(_pom_input(materialgruppe=gruppe))
        assert result.berechenbar is True, gruppe
        alpha_mm2_s = result.temperaturleitfaehigkeit_m2_s * 1e6
        assert 0.06 < alpha_mm2_s < 0.14, (gruppe, alpha_mm2_s)
        assert 0 < result.gesamtzykluszeit_s < 300, gruppe


# --------------------------------------------------------------------------------------
# Nebenzeiten und Größenklassen
# --------------------------------------------------------------------------------------


def test_groessenklassen_bleiben_informative_klassifizierung():
    assert DEFAULT_GROESSENKLASSE == "mittel"
    assert [key for key, _label in GROESSENKLASSEN] == ["klein", "mittel", "gross"]


def test_referenzbeispiel_grosses_bauteil_mit_greifer():
    """PP, 2.414 g, 1 Kavität, 2.653 t, 2,5 mm → rund 75,3 s."""
    result = berechne_zykluszeit(_referenz_input())
    assert result.berechenbar is True
    assert result.optimale_kuehlzeit_s == pytest.approx(11.04, abs=0.02)
    assert result.kuehlzeit_s == pytest.approx(16.56, abs=0.02)
    assert result.nebenzeit_werkzeugbewegung_s == pytest.approx(22.0)
    assert result.nebenzeit_einspritz_nachdruck_s == pytest.approx(15.98, abs=0.01)
    assert result.plastifizierleistung_kg_h == pytest.approx(330.0)
    assert result.nebenzeit_dosierzeit_s == pytest.approx(26.33, abs=0.02)
    assert result.nebenzeit_dosier_ueberhang_s == pytest.approx(9.77, abs=0.03)
    assert result.nebenzeit_entnahme_s == pytest.approx(11.0)
    assert result.nebenzeit_prozessaufwand_zuschlag_s == pytest.approx(0.0)
    assert result.nebenzeiten_gesamt_s == pytest.approx(58.75, abs=0.05)
    assert result.nebenzeit_quelle == "automatisch"
    assert result.entnahmeart == "greifer"
    assert result.gesamtzykluszeit_s == pytest.approx(75.31, abs=0.05)


def test_referenzbeispiel_werkzeugfallend():
    result = berechne_zykluszeit(_referenz_input(entnahmeart="werkzeugfallend"))
    assert result.nebenzeit_entnahme_s == pytest.approx(2.0)
    assert result.gesamtzykluszeit_s == pytest.approx(66.31, abs=0.05)


def test_referenzbeispiel_aufwendig():
    result = berechne_zykluszeit(_referenz_input(prozessaufwand="aufwendig"))
    assert result.nebenzeit_prozessaufwand_zuschlag_s == pytest.approx(
        PROZESSAUFWAND_ZUSCHLAG_S
    )
    assert result.gesamtzykluszeit_s == pytest.approx(80.31, abs=0.05)


@pytest.mark.parametrize(
    ("zuhaltekraft_t", "erwartet"),
    [
        (1.0, 4.0),
        (100.0, 4.0),
        (100.1, 6.0),
        (300.0, 6.0),
        (300.1, 10.0),
        (800.0, 10.0),
        (800.1, 14.0),
        (1500.0, 14.0),
        (1500.1, 18.0),
        (2500.0, 18.0),
        (2500.1, 22.0),
        (None, 6.0),
        (0.0, 6.0),
    ],
)
def test_werkzeugbewegungszeit_je_zuhaltekraftklasse(zuhaltekraft_t, erwartet):
    assert werkzeugbewegungszeit_s(zuhaltekraft_t) == pytest.approx(erwartet)


@pytest.mark.parametrize(
    ("schussgewicht_g", "erwartet"),
    [
        (1.0, 1.506),
        (0.5, 1.503),
        (100.0, 2.1),
        (2414.0, 15.984),
        (4750.0, SPRITZZEIT_MAX_S),
        (100000.0, SPRITZZEIT_MAX_S),
    ],
)
def test_einspritzzeit_aus_schussgewicht(schussgewicht_g, erwartet):
    assert einspritz_nachdruckzeit_s(schussgewicht_g) == pytest.approx(erwartet, abs=1e-6)
    assert SPRITZZEIT_MIN_S <= einspritz_nachdruckzeit_s(schussgewicht_g) <= SPRITZZEIT_MAX_S


def test_einspritzzeit_bleibt_in_den_grenzen():
    """Untergrenze 1,5 s (Grundzeit) und Obergrenze 30,0 s werden nie verlassen."""
    assert SPRITZZEIT_MIN_S == 1.5
    assert SPRITZZEIT_MAX_S == 30.0
    assert einspritz_nachdruckzeit_s(1e-9) == pytest.approx(SPRITZZEIT_MIN_S, abs=1e-6)
    assert einspritz_nachdruckzeit_s(4750.0) == pytest.approx(SPRITZZEIT_MAX_S)
    assert einspritz_nachdruckzeit_s(1e9) == pytest.approx(SPRITZZEIT_MAX_S)


@pytest.mark.parametrize("schussgewicht_g", [None, 0.0, -5.0])
def test_einspritzzeit_fallback_ohne_schussgewicht(schussgewicht_g):
    assert einspritz_nachdruckzeit_s(schussgewicht_g) == pytest.approx(
        SPRITZZEIT_OHNE_SCHUSSGEWICHT_S
    )
    result = berechne_zykluszeit(_pom_input(schussgewicht_g=schussgewicht_g))
    assert result.schussgewicht_fallback is True
    assert result.nebenzeit_einspritz_nachdruck_s == pytest.approx(
        SPRITZZEIT_OHNE_SCHUSSGEWICHT_S
    )


@pytest.mark.parametrize(
    ("zuhaltekraft_t", "erwartet"),
    [
        (100.0, 25.0),
        (300.0, 50.0),
        (800.0, 110.0),
        (1500.0, 200.0),
        (2500.0, 280.0),
        (2500.1, 330.0),
        (None, 50.0),
    ],
)
def test_plastifizierleistung_je_zuhaltekraftklasse(zuhaltekraft_t, erwartet):
    assert plastifizierleistung_kg_h(zuhaltekraft_t) == pytest.approx(erwartet)


def test_dosierueberhang_ist_null_wenn_dosierzeit_unter_kuehlzeit():
    """POM 4,5 mm kühlt lang; ein kleiner Schuss ist längst dosiert."""
    result = berechne_zykluszeit(
        _pom_input(schussgewicht_g=60.0, kavitaeten=1, zuhaltekraft_t=480.0)
    )
    assert result.nebenzeit_dosierzeit_s < result.kuehlzeit_s
    assert result.nebenzeit_dosier_ueberhang_s == pytest.approx(0.0)


def test_dosierueberhang_aus_schussgewicht_kavitaeten_und_leistung():
    result = berechne_zykluszeit(_referenz_input(kavitaeten=2))
    soll_dosier = dosierzeit_s(2414.0 * 2, 330.0)
    assert result.schussmasse_gesamt_g == pytest.approx(4828.0)
    assert result.nebenzeit_dosierzeit_s == pytest.approx(soll_dosier)
    assert result.nebenzeit_dosier_ueberhang_s == pytest.approx(
        soll_dosier - result.kuehlzeit_s
    )


def test_kavitaeten_erhoehen_die_kuehlzeit_nicht_aber_die_dosierzeit():
    einfach = berechne_zykluszeit(_referenz_input(kavitaeten=1))
    doppelt = berechne_zykluszeit(_referenz_input(kavitaeten=2))
    assert doppelt.kuehlzeit_s == pytest.approx(einfach.kuehlzeit_s)
    assert doppelt.nebenzeit_dosierzeit_s == pytest.approx(
        einfach.nebenzeit_dosierzeit_s * 2
    )
    assert doppelt.nebenzeit_dosier_ueberhang_s > einfach.nebenzeit_dosier_ueberhang_s


@pytest.mark.parametrize(
    ("entnahmeart", "zuhaltekraft_t", "erwartet"),
    [
        ("werkzeugfallend", 300.0, 1.0),
        ("werkzeugfallend", 300.1, 1.5),
        ("werkzeugfallend", 1500.0, 1.5),
        ("werkzeugfallend", 1500.1, 2.0),
        ("werkzeugfallend", None, 1.0),
        ("greifer", 300.0, 3.0),
        ("greifer", 300.1, 5.0),
        ("greifer", 800.0, 5.0),
        ("greifer", 800.1, 7.0),
        ("greifer", 1500.0, 7.0),
        ("greifer", 1500.1, 9.0),
        ("greifer", 2500.0, 9.0),
        ("greifer", 2500.1, 11.0),
        ("greifer", None, 5.0),
    ],
)
def test_entnahmezeit_je_art_und_zuhaltekraftklasse(entnahmeart, zuhaltekraft_t, erwartet):
    assert entnahmezeit_s(entnahmeart, zuhaltekraft_t, 1) == pytest.approx(erwartet)


def test_greifer_kavitaetenzuschlag_wird_begrenzt():
    basis = entnahmezeit_s("greifer", 400.0, 1)
    assert entnahmezeit_s("greifer", 400.0, 2) == pytest.approx(
        basis + ENTNAHME_GREIFER_JE_WEITERE_KAVITAET_S
    )
    assert entnahmezeit_s("greifer", 400.0, 5) == pytest.approx(
        basis + 4 * ENTNAHME_GREIFER_JE_WEITERE_KAVITAET_S
    )
    # 21 Kavitäten wären 4,0 s; ab 22 greift die Begrenzung.
    assert entnahmezeit_s("greifer", 400.0, 21) == pytest.approx(
        basis + ENTNAHME_GREIFER_KAVITAETEN_MAX_S
    )
    assert entnahmezeit_s("greifer", 400.0, 60) == pytest.approx(
        basis + ENTNAHME_GREIFER_KAVITAETEN_MAX_S
    )
    # Werkzeugfallend kennt keinen Kavitätenzuschlag.
    assert entnahmezeit_s("werkzeugfallend", 400.0, 60) == pytest.approx(
        entnahmezeit_s("werkzeugfallend", 400.0, 1)
    )


def test_nebenzeit_ist_summe_der_komponenten():
    result = berechne_zykluszeit(_referenz_input())
    assert result.nebenzeiten_automatisch_s == pytest.approx(
        result.nebenzeit_werkzeugbewegung_s
        + result.nebenzeit_einspritz_nachdruck_s
        + result.nebenzeit_dosier_ueberhang_s
        + result.nebenzeit_entnahme_s
        + result.nebenzeit_prozessaufwand_zuschlag_s
    )
    assert result.gesamtzykluszeit_s == pytest.approx(
        result.kuehlzeit_s + result.nebenzeiten_gesamt_s
    )


def test_prozessaufwand_zuschlag_wird_genau_einmal_addiert():
    normal = berechne_zykluszeit(_referenz_input(prozessaufwand="normal"))
    aufwendig = berechne_zykluszeit(_referenz_input(prozessaufwand="aufwendig"))
    assert PROZESSAUFWAND_ZUSCHLAG_S == 5.0
    assert aufwendig.nebenzeiten_gesamt_s == pytest.approx(
        normal.nebenzeiten_gesamt_s + PROZESSAUFWAND_ZUSCHLAG_S
    )
    assert aufwendig.gesamtzykluszeit_s == pytest.approx(
        normal.gesamtzykluszeit_s + PROZESSAUFWAND_ZUSCHLAG_S
    )


def test_eigene_nebenzeiten_uebersteuern_alle_komponenten():
    result = berechne_zykluszeit(_referenz_input(nebenzeiten_gesamt_s=21.5))
    assert result.nebenzeiten_gesamt_s == pytest.approx(21.5)
    assert result.nebenzeit_quelle == "manuell"
    assert result.gesamtzykluszeit_s == pytest.approx(result.kuehlzeit_s + 21.5)
    # Die Komponenten bleiben zur Nachvollziehbarkeit erhalten.
    assert result.nebenzeiten_automatisch_s == pytest.approx(58.75, abs=0.05)


@pytest.mark.parametrize("entnahmeart", ["greifer", "werkzeugfallend"])
@pytest.mark.parametrize("prozessaufwand", ["normal", "aufwendig"])
def test_manuelle_nebenzeit_ignoriert_entnahmeart_und_prozessaufwand(
    entnahmeart, prozessaufwand
):
    result = berechne_zykluszeit(
        _referenz_input(
            entnahmeart=entnahmeart,
            prozessaufwand=prozessaufwand,
            nebenzeiten_gesamt_s=7.0,
        )
    )
    assert result.nebenzeiten_gesamt_s == pytest.approx(7.0)
    assert result.nebenzeit_quelle == "manuell"


def test_negative_nebenzeiten_werden_abgelehnt():
    result = berechne_zykluszeit(_pom_input(nebenzeiten_gesamt_s=-1))
    assert result.berechenbar is False
    assert "nicht negativ" in result.hinweis


def test_fehlende_entnahmeart_nutzt_greifer():
    assert DEFAULT_ENTNAHMEART == "greifer"
    assert normalisiere_entnahmeart(None) == "greifer"
    assert normalisiere_entnahmeart("") == "greifer"
    assert normalisiere_entnahmeart("gibtsnicht") == "greifer"
    assert normalisiere_entnahmeart("WERKZEUGFALLEND") == "werkzeugfallend"
    ohne = berechne_zykluszeit(_referenz_input(entnahmeart=None))
    mit = berechne_zykluszeit(_referenz_input(entnahmeart="greifer"))
    assert ohne.entnahmeart == "greifer"
    assert ohne.gesamtzykluszeit_s == pytest.approx(mit.gesamtzykluszeit_s)


def test_fehlender_prozessaufwand_nutzt_normal():
    result = berechne_zykluszeit(_referenz_input(prozessaufwand=None))
    assert result.prozessaufwand == "normal"
    assert result.nebenzeit_prozessaufwand_zuschlag_s == pytest.approx(0.0)


def test_maschinen_zuhaltekraft_dient_als_ersatz():
    assert massgebliche_zuhaltekraft_t(2653.0, 3000.0) == pytest.approx(2653.0)
    assert massgebliche_zuhaltekraft_t(None, 3000.0) == pytest.approx(3000.0)
    assert massgebliche_zuhaltekraft_t(0.0, 3000.0) == pytest.approx(3000.0)
    assert massgebliche_zuhaltekraft_t(None, None) is None
    result = berechne_zykluszeit(
        _referenz_input(zuhaltekraft_t=None, maschinen_zuhaltekraft_t=2653.0)
    )
    assert result.zuhaltekraft_t == pytest.approx(2653.0)
    assert result.zuhaltekraft_fallback is False
    assert result.gesamtzykluszeit_s == pytest.approx(75.31, abs=0.05)


def test_fehlende_zuhaltekraft_weist_fallback_aus():
    result = berechne_zykluszeit(_referenz_input(zuhaltekraft_t=None))
    assert result.zuhaltekraft_fallback is True
    assert result.nebenzeit_werkzeugbewegung_s == pytest.approx(6.0)
    assert result.nebenzeit_entnahme_s == pytest.approx(5.0)
    assert result.plastifizierleistung_kg_h == pytest.approx(50.0)


def test_grossteil_warnung_blockiert_nicht():
    result = berechne_zykluszeit(_referenz_input(wandstaerke_mm=2.5))
    assert result.berechenbar is True
    assert GROSSTEIL_WARNUNG_TEXT in result.warnungen
    ohne_warnung = berechne_zykluszeit(_referenz_input(wandstaerke_mm=2.9))
    assert GROSSTEIL_WARNUNG_TEXT in ohne_warnung.warnungen
    # Die Warnung löst keinen Zuschlag aus.
    assert result.nebenzeiten_gesamt_s == pytest.approx(
        automatische_nebenzeiten(
            zuhaltekraft_t=2653.0,
            schussgewicht_g=2414.0,
            kavitaeten=1,
            entnahmeart="greifer",
            prozessaufwand="normal",
            kuehlzeit_s=result.kuehlzeit_s,
        ).gesamt_s
    )


@pytest.mark.parametrize(
    ("zuhaltekraft_t", "wandstaerke_mm"),
    [(2653.0, 3.0), (2653.0, 4.0), (800.0, 2.5), (None, 2.5)],
)
def test_grossteil_warnung_erscheint_nicht(zuhaltekraft_t, wandstaerke_mm):
    result = berechne_zykluszeit(
        _referenz_input(zuhaltekraft_t=zuhaltekraft_t, wandstaerke_mm=wandstaerke_mm)
    )
    assert result.warnungen == []


def test_ergebnis_enthaelt_keine_nan_oder_negativen_zeiten():
    for inp in (
        _referenz_input(),
        _referenz_input(kavitaeten=8, prozessaufwand="aufwendig"),
        _referenz_input(zuhaltekraft_t=None, schussgewicht_g=None),
        _pom_input(),
    ):
        result = berechne_zykluszeit(inp)
        for key, value in result.as_dict().items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            assert math.isfinite(value), key
            assert value >= 0, key


def test_amorph_liefert_naeherungs_hinweis_bleibt_aber_berechenbar():
    result = berechne_zykluszeit(_pom_input(materialgruppe="ABS"))
    assert result.berechenbar is True
    assert result.materialklasse == "amorph"
    assert result.hinweis is not None
    assert "vereinfachte Näherung" in result.hinweis


def test_teilkristallin_ohne_warnhinweis():
    result = berechne_zykluszeit(_pom_input(materialgruppe="POM"))
    assert result.berechenbar is True
    assert result.materialklasse == "teilkristallin"
    assert result.hinweis is None


def test_temperaturordnung_wird_geprueft(monkeypatch):
    from app.services import zykluszeit as zykluszeit_mod
    from app.services.material_thermik import ThermikDefaults

    bad = ThermikDefaults(
        "TEST", "Test", 1000.0, 2000.0, 0.2, 90.0, 100.0, 80.0  # T_E < T_W
    )
    monkeypatch.setattr(zykluszeit_mod, "defaults_fuer_gruppe", lambda _g: bad)
    result = berechne_zykluszeit(_pom_input(materialgruppe="TEST"))
    assert result.berechenbar is False
    assert "Entformungstemperatur" in (result.hinweis or "")


# --------------------------------------------------------------------------------------
# Werkzeugauslegung: Kavitäten wirken über die Zuhaltekraft
# --------------------------------------------------------------------------------------


def test_kavitaeten_verlaengern_die_kuehlzeit_nicht():
    """Alle Kavitäten kühlen gleichzeitig; nur die Nebenzeiten dürfen wachsen."""
    einfach = berechne_zykluszeit(_pom_input(groessenklasse="auto", zuhaltekraft_t=60.0))
    vierfach = berechne_zykluszeit(_pom_input(groessenklasse="auto", zuhaltekraft_t=240.0))
    assert vierfach.kuehlzeit_s == pytest.approx(einfach.kuehlzeit_s)
    assert vierfach.nebenzeiten_gesamt_s > einfach.nebenzeiten_gesamt_s


@pytest.mark.parametrize(
    ("zuhaltekraft_t", "erwartete_klasse"),
    [(1.0, "klein"), (99.9, "klein"), (100.0, "klein"), (100.1, "mittel"), (300.0, "mittel"),
     (300.1, "gross"), (1200.0, "gross")],
)
def test_auto_klasse_folgt_der_zuhaltekraft(zuhaltekraft_t: float, erwartete_klasse: str):
    assert klasse_aus_zuhaltekraft(zuhaltekraft_t) == erwartete_klasse
    result = berechne_zykluszeit(_pom_input(groessenklasse="auto", zuhaltekraft_t=zuhaltekraft_t))
    assert result.groessenklasse == erwartete_klasse
    assert result.groessenklasse_auswahl == "auto"
    assert result.zuhaltekraft_t == pytest.approx(zuhaltekraft_t)


def test_auto_ohne_zuhaltekraft_nutzt_den_default():
    for zuhaltekraft in (None, 0.0, -5.0):
        result = berechne_zykluszeit(_pom_input(groessenklasse="auto", zuhaltekraft_t=zuhaltekraft))
        assert result.groessenklasse == DEFAULT_GROESSENKLASSE
        assert result.groessenklasse_auswahl == GROESSENKLASSE_AUTO


def test_auto_ist_der_default_und_unbekannte_werte_landen_dort():
    assert DEFAULT_GROESSENKLASSE == "mittel"
    assert normalisiere_groessenklasse(None) == GROESSENKLASSE_AUTO
    assert normalisiere_groessenklasse("gibtsnicht") == GROESSENKLASSE_AUTO
    assert normalisiere_groessenklasse("KLEIN") == "klein"
    result = berechne_zykluszeit(_pom_input(zuhaltekraft_t=500.0))
    assert result.groessenklasse == "gross"


def test_manuelle_klasse_beeinflusst_die_nebenzeit_nicht_mehr():
    """Die Klasse ist nur noch informativ; die Nebenzeit folgt der Zuhaltekraft."""
    manuell = berechne_zykluszeit(_pom_input(groessenklasse="klein", zuhaltekraft_t=800.0))
    automatisch = berechne_zykluszeit(_pom_input(groessenklasse="auto", zuhaltekraft_t=800.0))
    assert manuell.groessenklasse == "klein"
    assert manuell.groessenklasse_auswahl == "klein"
    assert manuell.nebenzeiten_gesamt_s == pytest.approx(automatisch.nebenzeiten_gesamt_s)


def test_eigene_nebenzeiten_uebersteuern_auch_die_auto_klasse():
    result = berechne_zykluszeit(
        _pom_input(groessenklasse="auto", zuhaltekraft_t=800.0, nebenzeiten_gesamt_s=7.0)
    )
    assert result.groessenklasse == "gross"
    assert result.nebenzeiten_gesamt_s == pytest.approx(7.0)


def test_teilergebnis_traegt_die_auto_aufloesung_mit():
    result = berechne_zykluszeit(
        _pom_input(wandstaerke_mm=None, groessenklasse="auto", zuhaltekraft_t=500.0)
    )
    assert result.berechenbar is False
    assert result.groessenklasse == "gross"
    assert result.groessenklasse_auswahl == GROESSENKLASSE_AUTO
    # 10,0 s Werkzeugbewegung (500 t) + 3,0 s Einspritz-Fallback + 5,0 s Greifer.
    assert result.nebenzeiten_gesamt_s == pytest.approx(18.0)


def test_zuhaltekraft_aus_kavitaeten_hebt_die_klasse():
    """4 Kavitäten eines Teils, das einfach noch als klein durchginge."""
    einfach = berechne_maschinen_groesse(
        MaschinenGroesseInput(
            modus="flaeche",
            injection_pressure_kg_cm2=500.0,
            kavitaeten=1,
            proj_flaeche_mm2=12000.0,
        )
    )
    vierfach = berechne_maschinen_groesse(
        MaschinenGroesseInput(
            modus="flaeche",
            injection_pressure_kg_cm2=500.0,
            kavitaeten=4,
            proj_flaeche_mm2=12000.0,
        )
    )
    assert vierfach.zuhaltekraft_erforderlich_t == pytest.approx(
        einfach.zuhaltekraft_erforderlich_t * 4
    )
    assert klasse_aus_zuhaltekraft(einfach.zuhaltekraft_erforderlich_t) == "klein"
    assert klasse_aus_zuhaltekraft(vierfach.zuhaltekraft_erforderlich_t) == "mittel"


# --------------------------------------------------------------------------------------
# Validierung
# --------------------------------------------------------------------------------------


def test_fehlende_materialgruppe_liefert_hinweis():
    result = berechne_zykluszeit(_pom_input(materialgruppe=None))
    assert result.berechenbar is False
    assert "Materialgruppe" in result.hinweis
    assert result.gesamtzykluszeit_s is None
    # Die Nebenzeiten bleiben trotzdem sichtbar.
    assert result.nebenzeiten_gesamt_s == pytest.approx(POM_AUTO_NEBENZEIT_S)


def test_unbekannte_materialgruppe_liefert_hinweis():
    result = berechne_zykluszeit(_pom_input(materialgruppe="Wundermaterial"))
    assert result.berechenbar is False
    assert "Materialgruppe" in result.hinweis


def test_fehlende_wandstaerke_liefert_hinweis():
    result = berechne_zykluszeit(_pom_input(wandstaerke_mm=None))
    assert result.berechenbar is False
    assert "kühlzeitrelevante Wandstärke" in result.hinweis


@pytest.mark.parametrize("wandstaerke", [0, -1.5, float("nan"), MAX_WANDSTAERKE_MM + 1])
def test_ungueltige_wandstaerke_liefert_hinweis(wandstaerke):
    result = berechne_zykluszeit(_pom_input(wandstaerke_mm=wandstaerke))
    assert result.berechenbar is False
    assert result.gesamtzykluszeit_s is None


def test_temperaturreihenfolge_der_tabelle_ist_gueltig():
    """T_Werkzeug < T_Entformung < T_Schmelze sichert ein positives ln-Argument."""
    for gruppe, werte in MATERIALGRUPPEN_DEFAULTS.items():
        assert werte.werkzeugtemperatur_c < werte.entformungstemperatur_c, gruppe
        assert werte.entformungstemperatur_c < werte.schmelzetemperatur_c, gruppe
        quotient = (werte.schmelzetemperatur_c - werte.werkzeugtemperatur_c) / (
            werte.entformungstemperatur_c - werte.werkzeugtemperatur_c
        )
        assert (4.0 / math.pi) * quotient > 1.0, gruppe


def test_kennwerte_der_tabelle_sind_positiv():
    """Schützt gegen Division durch 0 in α = λ / (ρ · c_p)."""
    for gruppe, werte in MATERIALGRUPPEN_DEFAULTS.items():
        assert werte.schmelzdichte_kg_m3 > 0, gruppe
        assert werte.waermekapazitaet_j_kg_k > 0, gruppe
        assert werte.waermeleitfaehigkeit_w_m_k > 0, gruppe


def test_defekte_gruppentabelle_wird_abgefangen(monkeypatch):
    kaputt = MATERIALGRUPPEN_DEFAULTS["POM"].__class__(
        gruppe="TEST",
        bezeichnung="Testharz",
        schmelzdichte_kg_m3=0.0,
        waermekapazitaet_j_kg_k=3000.0,
        waermeleitfaehigkeit_w_m_k=0.27,
        werkzeugtemperatur_c=40.0,
        schmelzetemperatur_c=220.0,
        entformungstemperatur_c=80.0,
    )
    monkeypatch.setitem(MATERIALGRUPPEN_DEFAULTS, "TEST", kaputt)
    result = berechne_zykluszeit(_pom_input(materialgruppe="TEST"))
    assert result.berechenbar is False
    assert "ungültig" in result.hinweis


# --------------------------------------------------------------------------------------
# Materialgruppen-Stammdaten
# --------------------------------------------------------------------------------------


def test_pom_defaults_stammen_aus_iket():
    pom = defaults_fuer_gruppe("POM")
    assert pom is not None
    for feld, wert in POM.items():
        assert getattr(pom, feld) == pytest.approx(wert)


def test_gruppenschreibweisen_werden_normalisiert():
    assert normalisiere_gruppe(" pom ") == "POM"
    assert normalisiere_gruppe("hdpe") == "PE-HD"
    assert normalisiere_gruppe("pe_ld") == "PE-LD"
    assert normalisiere_gruppe("") is None
    assert normalisiere_gruppe("XYZ") == "XYZ"


def test_material_schema_normalisiert_gruppe():
    mat = MaterialCreate(
        bezeichnung="Delrin",
        material_nr="POM-1",
        preis_pro_kg="2,10",
        dichte="1,41",
        materialgruppe="pom",
    )
    assert mat.materialgruppe == "POM"


def test_material_lehnt_unbekannte_gruppe_ab(client: TestClient):
    res = client.post(
        f"{API}/materialien",
        json={
            "bezeichnung": "X",
            "material_nr": "X-1",
            "preis_pro_kg": 1,
            "dichte": 1,
            "materialgruppe": "XYZ",
        },
    )
    assert res.status_code == 422, res.text
    assert "Unbekannte Materialgruppe" in res.text


# --------------------------------------------------------------------------------------
# Persistenz und API
# --------------------------------------------------------------------------------------


def _material_schema(engine) -> None:
    create_material_tables(engine)


@pytest.fixture()
def db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _material_schema(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    seed_materialgruppen(session)
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db: Session) -> TestClient:
    application = FastAPI()
    application.include_router(api_router)

    def override_get_db():
        yield db

    def override_user():
        return SimpleNamespace(
            email="kalkulator@example.com",
            role=UserRole.KALKULATOR.value,
            is_active=True,
        )

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_current_user] = override_user
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def test_materialgruppen_endpoint(client: TestClient):
    res = client.get(f"{API}/materialien/materialgruppen")
    assert res.status_code == 200, res.text
    gruppen = {row["gruppe"]: row for row in res.json()}
    assert gruppen["POM"]["schmelzdichte_kg_m3"] == pytest.approx(783.17)
    assert set(gruppen) == set(MATERIALGRUPPEN_DEFAULTS)


def test_materialgruppe_speichern_und_laden(client: TestClient, db: Session):
    res = client.post(
        f"{API}/materialien",
        json={
            "bezeichnung": "Delrin 500P NC010",
            "material_nr": "POM-IKET",
            "preis_pro_kg": "2,10",
            "dichte": "1,41",
            "materialgruppe": "pom",
        },
    )
    assert res.status_code == 201, res.text
    mid = res.json()["id"]
    assert res.json()["materialgruppe"] == "POM"
    assert db.query(Material).filter(Material.id == mid).one().materialgruppe == "POM"

    upd = client.put(f"{API}/materialien/{mid}", json={"materialgruppe": "PP"})
    assert upd.status_code == 200, upd.text
    assert client.get(f"{API}/materialien/{mid}").json()["materialgruppe"] == "PP"


def test_material_ohne_gruppe_bleibt_leer(client: TestClient):
    res = client.post(
        f"{API}/materialien",
        json={
            "bezeichnung": "Unbekannter Compound",
            "material_nr": "UNK-1",
            "preis_pro_kg": "3,00",
            "dichte": "1,10",
        },
    )
    assert res.status_code == 201, res.text
    assert res.json()["materialgruppe"] is None


def _pom_material_ueber_api(client: TestClient, material_nr: str) -> int:
    res = client.post(
        f"{API}/materialien",
        json={
            "bezeichnung": "Delrin 500P NC010",
            "material_nr": material_nr,
            "preis_pro_kg": "2,10",
            "dichte": "1,41",
            "materialgruppe": "POM",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_preview_endpoint_pom(client: TestClient):
    material_id = _pom_material_ueber_api(client, "POM-PREV")
    res = client.post(
        f"{API}/spritzguss/zykluszeit/berechnen",
        json={
            "material_id": material_id,
            "zykluszeit_wandstaerke_mm": "4,5",
            "zykluszeit_nebenzeiten_gesamt_s": "12,5",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    _alpha, t_opt_soll = _erwartete_kuehlzeit(wandstaerke_mm=POM_WANDSTAERKE_MM, **POM)
    assert body["berechenbar"] is True
    assert body["materialgruppe"] == "POM"
    assert body["optimale_kuehlzeit_s"] == pytest.approx(t_opt_soll)
    assert body["gesamtzykluszeit_s"] == pytest.approx(t_opt_soll * 1.5 + 12.5)


def test_preview_endpoint_nutzt_groessenklasse(client: TestClient):
    material_id = _pom_material_ueber_api(client, "POM-KLASSE")
    res = client.post(
        f"{API}/spritzguss/zykluszeit/berechnen",
        json={
            "material_id": material_id,
            "zykluszeit_wandstaerke_mm": "4,5",
            "zykluszeit_groessenklasse": "klein",
        },
    )
    body = res.json()
    assert body["groessenklasse"] == "klein"
    assert body["nebenzeiten_gesamt_s"] == pytest.approx(POM_AUTO_NEBENZEIT_S)


def test_preview_ohne_material_liefert_hinweis(client: TestClient):
    res = client.post(
        f"{API}/spritzguss/zykluszeit/berechnen",
        json={"zykluszeit_wandstaerke_mm": "3,0"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["berechenbar"] is False
    assert "Materialgruppe" in res.json()["hinweis"]


def test_schema_quelle_nur_manuell_oder_vorschlag():
    assert ZykluszeitFields(zykluszeit_quelle="vorschlag").zykluszeit_quelle == "vorschlag"
    with pytest.raises(Exception, match="manuell"):
        ZykluszeitFields(zykluszeit_quelle="irgendwas")


def test_schema_lehnt_ungueltige_groessenklasse_ab():
    assert ZykluszeitFields(zykluszeit_groessenklasse="GROSS").zykluszeit_groessenklasse == "gross"
    assert ZykluszeitFields(zykluszeit_groessenklasse="auto").zykluszeit_groessenklasse == "auto"
    with pytest.raises(Exception, match="Größenklasse"):
        ZykluszeitFields(zykluszeit_groessenklasse="riesig")


def test_schema_prozessaufwand_normalisierung():
    assert ZykluszeitFields(zykluszeit_prozessaufwand="AUFWENDIG").zykluszeit_prozessaufwand == "aufwendig"
    assert ZykluszeitFields().zykluszeit_prozessaufwand is None
    with pytest.raises(Exception, match="Prozessaufwand"):
        ZykluszeitFields(zykluszeit_prozessaufwand="extrem")


def test_schema_entnahmeart_normalisierung():
    assert (
        ZykluszeitFields(zykluszeit_entnahmeart="GREIFER").zykluszeit_entnahmeart == "greifer"
    )
    assert ZykluszeitFields().zykluszeit_entnahmeart is None
    with pytest.raises(Exception, match="Entnahmeart"):
        ZykluszeitFields(zykluszeit_entnahmeart="handentnahme")


def test_preview_endpoint_liefert_identische_werte_wie_der_service(client: TestClient, db: Session):
    """Punkt 22: API und Service (und damit das Frontend) rechnen gleich."""
    db.add(
        Material(
            bezeichnung="PP Copo",
            material_nr="PP-REF",
            preis_pro_kg=1.4,
            dichte=0.92,
            materialgruppe="PP",
        )
    )
    db.flush()
    material_id = db.query(Material).filter(Material.material_nr == "PP-REF").one().id

    res = client.post(
        f"{API}/spritzguss/zykluszeit/berechnen",
        json={
            "material_id": material_id,
            "zykluszeit_wandstaerke_mm": "2,5",
            "zykluszeit_entnahmeart": "greifer",
            "zykluszeit_prozessaufwand": "normal",
            "zuhaltekraft_t": "2653",
            "schussgewicht_g": "2414",
            "kavitaeten": 1,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    soll = berechne_zykluszeit(_referenz_input(), db=db).as_dict()
    for key in (
        "kuehlzeit_s",
        "nebenzeit_werkzeugbewegung_s",
        "nebenzeit_einspritz_nachdruck_s",
        "nebenzeit_dosierzeit_s",
        "nebenzeit_dosier_ueberhang_s",
        "nebenzeit_entnahme_s",
        "nebenzeit_prozessaufwand_zuschlag_s",
        "plastifizierleistung_kg_h",
        "schussmasse_gesamt_g",
        "nebenzeiten_automatisch_s",
        "nebenzeiten_gesamt_s",
        "gesamtzykluszeit_s",
    ):
        assert body[key] == pytest.approx(soll[key]), key
    assert body["entnahmeart"] == "greifer"
    assert body["warnungen"] == [GROSSTEIL_WARNUNG_TEXT]
    assert body["gesamtzykluszeit_s"] == pytest.approx(75.31, abs=0.05)


def test_preview_endpoint_leitet_klasse_aus_zuhaltekraft_ab(client: TestClient):
    material_id = _pom_material_ueber_api(client, "POM-AUTO")

    def preview(zuhaltekraft_t: float | None) -> dict:
        return client.post(
            f"{API}/spritzguss/zykluszeit/berechnen",
            json={
                "material_id": material_id,
                "zykluszeit_wandstaerke_mm": "4,5",
                "zykluszeit_groessenklasse": "auto",
                "zuhaltekraft_t": zuhaltekraft_t,
            },
        ).json()

    klein = preview(80.0)
    gross = preview(650.0)
    assert klein["groessenklasse"] == "klein"
    # 4,0 s Werkzeugbewegung + 3,0 s Einspritz-Fallback + 3,0 s Greifer.
    assert klein["nebenzeiten_gesamt_s"] == pytest.approx(10.0)
    assert gross["groessenklasse"] == "gross"
    assert gross["groessenklasse_auswahl"] == "auto"
    assert gross["zuhaltekraft_t"] == pytest.approx(650.0)
    # 10,0 s Werkzeugbewegung + 3,0 s Einspritz-Fallback + 5,0 s Greifer.
    assert gross["nebenzeiten_gesamt_s"] == pytest.approx(18.0)
    # Nur die Nebenzeiten unterscheiden sich, die Kühlzeit bleibt gleich.
    assert gross["kuehlzeit_s"] == pytest.approx(klein["kuehlzeit_s"])


# --------------------------------------------------------------------------------------
# Datensatz, Export und Folgewirkung auf Kosten/Kapazität
# --------------------------------------------------------------------------------------


def _spritzguss_input(zykluszeit_s: float) -> SpritzgussInput:
    return SpritzgussInput(
        teilegewicht_netto_g=50,
        schussgewicht_g=60,
        materialpreis_pro_kg=2.5,
        ausschussquote_pct=2,
        mgk_pct=5,
        zykluszeit_s=zykluszeit_s,
        maschinenstundensatz=60,
        kavitaeten=4,
        lohnstundensatz=30,
        fgk_pct=10,
        werkzeugkosten_eur=20000,
        werkzeug_abrechnungsart="amortisation",
        amortisationsvolumen=100000,
        vvgk_pct=8,
        gewinn_pct=5,
        skonto_pct=2,
    )


def _kalkulation_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE spritzguss_kalkulationen (
                    id INTEGER PRIMARY KEY,
                    teilebezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                    teilenummer VARCHAR(100) NOT NULL DEFAULT '',
                    kunde VARCHAR(255) NOT NULL DEFAULT '',
                    projekt VARCHAR(255) NOT NULL DEFAULT '',
                    jahresstueckzahl INTEGER NOT NULL DEFAULT 0,
                    customer_id INTEGER,
                    program_id INTEGER,
                    project_id INTEGER,
                    calculation_year INTEGER,
                    project_volume FLOAT,
                    werk_id INTEGER,
                    losgroesse INTEGER,
                    losgroesse_modus VARCHAR(16),
                    losgroesse_manuell INTEGER,
                    material_id INTEGER,
                    schussgewicht_g FLOAT NOT NULL DEFAULT 0,
                    teilegewicht_netto_g FLOAT NOT NULL DEFAULT 100,
                    ausschussquote_pct FLOAT NOT NULL DEFAULT 0,
                    materialpreis_pro_kg FLOAT NOT NULL DEFAULT 0,
                    material_nominierung VARCHAR(32),
                    maschine_id INTEGER,
                    zykluszeit_s FLOAT NOT NULL DEFAULT 0,
                    kavitaeten INTEGER NOT NULL DEFAULT 1,
                    maschinenstundensatz FLOAT NOT NULL DEFAULT 0,
                    lohnkosten_id INTEGER,
                    lohnstundensatz FLOAT NOT NULL DEFAULT 0,
                    werkzeug_abrechnungsart VARCHAR(32) NOT NULL DEFAULT 'amortisation',
                    werkzeugkosten_eur FLOAT NOT NULL DEFAULT 0,
                    amortisationsvolumen INTEGER,
                    mgk_pct FLOAT NOT NULL DEFAULT 0,
                    fgk_pct FLOAT NOT NULL DEFAULT 0,
                    vvgk_pct FLOAT NOT NULL DEFAULT 0,
                    gewinn_pct FLOAT NOT NULL DEFAULT 0,
                    skonto_pct FLOAT NOT NULL DEFAULT 0,
                    ergebnis TEXT,
                    ergebnis_bloecke TEXT,
                    notizen TEXT NOT NULL DEFAULT '',
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    maschinen_groesse_modus VARCHAR(16),
                    maschinen_groesse_breite_mm FLOAT,
                    maschinen_groesse_laenge_mm FLOAT,
                    maschinen_groesse_oeffnungen_pct FLOAT,
                    maschinen_groesse_proj_flaeche_mm2 FLOAT,
                    maschinen_groesse_schwindung_pct FLOAT,
                    maschinen_groesse_injection_pressure_kg_cm2 FLOAT,
                    maschinen_groesse_proj_flaeche_netto_mm2 FLOAT,
                    maschinen_groesse_zuhaltekraft_ohne_sicherheit_t FLOAT,
                    maschinen_groesse_sicherheitszuschlag_faktor FLOAT,
                    maschinen_groesse_zuhaltekraft_erforderlich_t FLOAT,
                    maschinen_groesse_empfohlene_maschine_id INTEGER,
                    maschinen_groesse_warnung VARCHAR(512),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    zykluszeit_quelle VARCHAR(16),
                    zykluszeit_wandstaerke_mm FLOAT,
                    zykluszeit_groessenklasse VARCHAR(16),
                    zykluszeit_prozessaufwand VARCHAR(16),
                    zykluszeit_entnahmeart VARCHAR(16),
                    zykluszeit_kuehlzeit_s FLOAT,
                    zykluszeit_nebenzeiten_gesamt_s FLOAT,
                    zykluszeit_vorschlag_s FLOAT,
                    zykluszeit_hinweis VARCHAR(512),
                    teilbild_mime VARCHAR(64),
                    teilbild_data TEXT
                )
                """
            )
        )


@pytest.fixture()
def kalk_db() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _material_schema(engine)
    _kalkulation_schema(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = factory()
    seed_materialgruppen(session)
    try:
        yield session
    finally:
        session.close()


def _pom_material(db: Session) -> Material:
    material = Material(
        bezeichnung="Delrin 500P NC010",
        material_nr="POM-DB",
        preis_pro_kg=2.1,
        dichte=1.41,
        materialgruppe="POM",
    )
    db.add(material)
    db.flush()
    return material


def _kalkulation(**overrides) -> SpritzgussKalkulation:
    daten = {
        "teilebezeichnung": "Halter",
        "teilenummer": "HLT-1",
        "teilegewicht_netto_g": 50.0,
        "schussgewicht_g": 60.0,
        "ausschussquote_pct": 2.0,
        "materialpreis_pro_kg": 2.5,
        "maschinenstundensatz": 60.0,
        "lohnstundensatz": 30.0,
        "werkzeugkosten_eur": 0.0,
        "zykluszeit_s": 30.0,
        "kavitaeten": 1,
    }
    daten.update(overrides)
    return SpritzgussKalkulation(**daten)


def test_schaetzung_am_datensatz_wird_berechnet_und_gespeichert(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(
        material_id=material.id,
        zykluszeit_wandstaerke_mm=POM_WANDSTAERKE_MM,
        zykluszeit_groessenklasse="mittel",
        zykluszeit_quelle="manuell",
    )
    kalk_db.add(obj)
    kalk_db.flush()

    result = _run_zykluszeit_for_model(kalk_db, obj)
    kalk_db.commit()
    assert result is not None and result.berechenbar is True

    _alpha, t_opt_soll = _erwartete_kuehlzeit(wandstaerke_mm=POM_WANDSTAERKE_MM, **POM)
    # 60 g Schuss, 1 Kavität, keine Zuhaltekraft: 6,0 + 1,86 + 0,0 + 5,0 s.
    soll_nebenzeit = 6.0 + einspritz_nachdruckzeit_s(60.0) + 5.0
    kalk_db.expire_all()
    geladen = kalk_db.get(SpritzgussKalkulation, obj.id)
    assert geladen.zykluszeit_kuehlzeit_s == pytest.approx(t_opt_soll * 1.5)
    assert geladen.zykluszeit_vorschlag_s == pytest.approx(t_opt_soll * 1.5 + soll_nebenzeit)
    assert geladen.zykluszeit_hinweis is None
    # Der Vorschlag überschreibt die bestehende Zykluszeit nicht.
    assert geladen.zykluszeit_s == pytest.approx(30.0)
    assert geladen.zykluszeit_quelle == "manuell"


def test_datensatz_nutzt_gespeicherte_zuhaltekraft_fuer_die_auto_klasse(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(
        material_id=material.id,
        zykluszeit_wandstaerke_mm=POM_WANDSTAERKE_MM,
        zykluszeit_groessenklasse="auto",
        kavitaeten=4,
        maschinen_groesse_zuhaltekraft_erforderlich_t=480.0,
    )
    kalk_db.add(obj)
    kalk_db.flush()

    result = _run_zykluszeit_for_model(kalk_db, obj)
    assert result.groessenklasse == "gross"
    assert result.zuhaltekraft_t == pytest.approx(480.0)
    # 10,0 s Werkzeugbewegung (480 t) + Einspritzzeit (60 g) + 0,0 s Dosierüberhang
    # + 5,0 s Greifer + 3 × 0,2 s Kavitätenzuschlag.
    soll_nebenzeit = 10.0 + einspritz_nachdruckzeit_s(60.0) + 5.0 + 0.6
    assert result.nebenzeit_dosier_ueberhang_s == pytest.approx(0.0)
    assert result.nebenzeiten_gesamt_s == pytest.approx(soll_nebenzeit)
    assert obj.zykluszeit_vorschlag_s == pytest.approx(result.kuehlzeit_s + soll_nebenzeit)


def test_eigene_nebenzeiten_bleiben_beim_neuberechnen_erhalten(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(
        material_id=material.id,
        zykluszeit_wandstaerke_mm=POM_WANDSTAERKE_MM,
        zykluszeit_groessenklasse="klein",
        zykluszeit_nebenzeiten_gesamt_s=13.0,
    )
    kalk_db.add(obj)
    kalk_db.flush()

    erst = _run_zykluszeit_for_model(kalk_db, obj)
    zweit = _run_zykluszeit_for_model(kalk_db, obj)
    assert erst.nebenzeiten_gesamt_s == pytest.approx(13.0)
    assert zweit.nebenzeiten_gesamt_s == pytest.approx(13.0)
    assert obj.zykluszeit_nebenzeiten_gesamt_s == pytest.approx(13.0)


def test_uebernommene_zykluszeit_bleibt_als_quelle_erhalten(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(
        material_id=material.id,
        zykluszeit_wandstaerke_mm=POM_WANDSTAERKE_MM,
        zykluszeit_quelle="vorschlag",
    )
    kalk_db.add(obj)
    kalk_db.flush()
    result = _run_zykluszeit_for_model(kalk_db, obj)
    obj.zykluszeit_s = result.gesamtzykluszeit_s
    kalk_db.commit()

    kalk_db.expire_all()
    geladen = kalk_db.get(SpritzgussKalkulation, obj.id)
    assert geladen.zykluszeit_quelle == "vorschlag"
    assert geladen.zykluszeit_s == pytest.approx(geladen.zykluszeit_vorschlag_s)


def test_ohne_wandstaerke_werden_ergebnisspalten_geleert(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(material_id=material.id, zykluszeit_vorschlag_s=99.0)
    kalk_db.add(obj)
    kalk_db.flush()

    assert _run_zykluszeit_for_model(kalk_db, obj) is None
    assert obj.zykluszeit_vorschlag_s is None
    assert obj.zykluszeit_hinweis is None


def test_material_ohne_gruppe_liefert_hinweis_am_datensatz(kalk_db: Session):
    material = Material(
        bezeichnung="Compound ohne Gruppe",
        material_nr="NO-GROUP",
        preis_pro_kg=2.0,
        dichte=1.0,
    )
    kalk_db.add(material)
    kalk_db.flush()
    obj = _kalkulation(material_id=material.id, zykluszeit_wandstaerke_mm=3.0)
    kalk_db.add(obj)
    kalk_db.flush()

    result = _run_zykluszeit_for_model(kalk_db, obj)
    assert result.berechenbar is False
    assert "Materialgruppe" in obj.zykluszeit_hinweis
    assert obj.zykluszeit_vorschlag_s is None


def test_export_rows_aus_ergebnis_und_orm(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(
        material_id=material.id,
        zykluszeit_wandstaerke_mm=POM_WANDSTAERKE_MM,
        zykluszeit_groessenklasse="mittel",
        zykluszeit_quelle="vorschlag",
    )
    kalk_db.add(obj)
    kalk_db.flush()
    result = _run_zykluszeit_for_model(kalk_db, obj)

    aus_ergebnis = {
        row.label: row.value
        for row in _zykluszeit_export_rows(obj, {"zykluszeit_vorschlag": result.as_dict()})
    }
    assert aus_ergebnis["Zykluszeit Quelle"] == "Übernommen aus Zykluszeit-Schätzung"
    assert aus_ergebnis["kühlzeitrelevante Wandstärke"] == "4.50 mm"
    assert aus_ergebnis["Materialgruppe"] == "POM"
    assert aus_ergebnis["Prozessaufwand"] == "normal"
    assert aus_ergebnis["Entnahmeart"] == "greifer"
    assert aus_ergebnis["Nebenzeit Werkzeugbewegung"] == "6.00 s"
    assert aus_ergebnis["Nebenzeit Einspritzen und Nachdruck"] == "1.86 s"
    assert aus_ergebnis["Nebenzeit Entnahme"] == "5.00 s"
    assert aus_ergebnis["Nebenzeit Prozessaufwand"] == "0.00 s"
    assert "Dosierzeit" in aus_ergebnis["Nebenzeit Dosierüberhang"]
    assert "Plastifizierleistung 50 kg/h" in aus_ergebnis["Nebenzeit Dosierüberhang"]
    assert aus_ergebnis["Nebenzeiten gesamt"] == "12.86 s"
    assert aus_ergebnis["Nebenzeit automatisch gesamt"] == "12.86 s"
    assert aus_ergebnis["Nebenzeit Quelle"] == "automatisch"
    assert aus_ergebnis["Zykluszeit-Schätzung gesamt"] == "59.61 s"

    # Paritätsprüfung: die gespeicherten Spalten liefern dieselben Kernwerte.
    aus_orm = {row.label: row.value for row in _zykluszeit_export_rows(obj, {})}
    for label in ("Kühlzeit inkl. Zuschlag 1,5", "Zykluszeit-Schätzung gesamt"):
        assert aus_orm[label] == aus_ergebnis[label]


def test_export_enthaelt_warnung_bei_grossem_werkzeug_und_duenner_wand(kalk_db: Session):
    material = Material(
        bezeichnung="PP Copo",
        material_nr="PP-EXP",
        preis_pro_kg=1.4,
        dichte=0.92,
        materialgruppe="PP",
    )
    kalk_db.add(material)
    kalk_db.flush()
    obj = _kalkulation(
        material_id=material.id,
        schussgewicht_g=2414.0,
        kavitaeten=1,
        zykluszeit_wandstaerke_mm=2.5,
        zykluszeit_entnahmeart="greifer",
        maschinen_groesse_zuhaltekraft_erforderlich_t=2653.0,
    )
    kalk_db.add(obj)
    kalk_db.flush()
    result = _run_zykluszeit_for_model(kalk_db, obj)

    assert result.gesamtzykluszeit_s == pytest.approx(75.31, abs=0.05)
    rows = {
        row.label: row.value
        for row in _zykluszeit_export_rows(obj, {"zykluszeit_vorschlag": result.as_dict()})
    }
    assert rows["Zykluszeit-Schätzung Warnung"] == GROSSTEIL_WARNUNG_TEXT
    assert rows["Nebenzeit Werkzeugbewegung"] == "22.00 s"
    assert rows["Nebenzeit Entnahme"] == "11.00 s"


def test_entnahmeart_bleibt_beim_neuladen_erhalten(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(
        material_id=material.id,
        zykluszeit_wandstaerke_mm=POM_WANDSTAERKE_MM,
        zykluszeit_entnahmeart="werkzeugfallend",
    )
    kalk_db.add(obj)
    kalk_db.flush()
    result = _run_zykluszeit_for_model(kalk_db, obj)
    kalk_db.commit()
    kalk_db.expire_all()

    geladen = kalk_db.get(SpritzgussKalkulation, obj.id)
    assert geladen.zykluszeit_entnahmeart == "werkzeugfallend"
    assert result.entnahmeart == "werkzeugfallend"
    erneut = _run_zykluszeit_for_model(kalk_db, geladen)
    assert erneut.gesamtzykluszeit_s == pytest.approx(result.gesamtzykluszeit_s)


def test_datensatz_ohne_entnahmeart_nutzt_greifer(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(
        material_id=material.id,
        zykluszeit_wandstaerke_mm=POM_WANDSTAERKE_MM,
        zykluszeit_entnahmeart=None,
    )
    kalk_db.add(obj)
    kalk_db.flush()
    result = _run_zykluszeit_for_model(kalk_db, obj)
    assert result.entnahmeart == "greifer"


def test_export_rows_ohne_schaetzung_zeigen_nur_quelle():
    obj = _kalkulation(zykluszeit_quelle="manuell")
    rows = _zykluszeit_export_rows(obj, {})
    assert [row.label for row in rows] == ["Zykluszeit Quelle"]
    assert rows[0].value == "Manuell erfasst"


def test_uebernommene_zykluszeit_wirkt_auf_kosten_und_kapazitaet():
    """Nach "Übernehmen" rechnet die Kostenlogik mit dem Vorschlagswert."""
    vorschlag = berechne_zykluszeit(_pom_input())
    assert vorschlag.berechenbar is True

    vorher = berechne_spritzguss(_spritzguss_input(30.0))
    nachher = berechne_spritzguss(_spritzguss_input(vorschlag.gesamtzykluszeit_s))

    erwartete_brutto = round((3600 / vorschlag.gesamtzykluszeit_s) * 4)
    assert nachher.bruttokapazitaet == pytest.approx(erwartete_brutto)
    assert nachher.bruttokapazitaet < vorher.bruttokapazitaet
    assert nachher.maschinenkosten > vorher.maschinenkosten
    assert nachher.fertigungslohn > vorher.fertigungslohn

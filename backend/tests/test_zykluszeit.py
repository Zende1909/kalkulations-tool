"""Tests für den Zykluszeitvorschlag nach IKET (Blatt "Zykluszeitbestimmung")."""

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
from app.schemas.material import MaterialCreate, MaterialUpdate
from app.services.export_builders import _zykluszeit_export_rows
from app.schemas.zykluszeit import ZykluszeitFields
from app.services.material_thermik import (
    MATERIALGRUPPEN_DEFAULTS,
    QUELLE_IKET,
    defaults_fuer_gruppe,
)
from app.services.spritzguss_kalkulation import SpritzgussInput, berechne_spritzguss
from app.services.zykluszeit import (
    DEFAULT_KUEHLFAKTOR,
    DEFAULT_NEBENZEITEN,
    DEFAULT_VARIANTE,
    NEBENZEIT_KEYS,
    ZykluszeitInput,
    berechne_zykluszeit,
    summe_nebenzeiten,
    temperaturleitfaehigkeit,
    variantenfaktor,
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


def _pom_input(**overrides) -> ZykluszeitInput:
    kwargs = {
        **POM,
        "wandstaerke_mm": POM_WANDSTAERKE_MM,
        "variante": 2,
        "kuehlfaktor": 1.5,
    }
    kwargs.update(overrides)
    return ZykluszeitInput(**kwargs)


def _erwartete_kuehlzeit(
    *,
    wandstaerke_mm: float,
    variante: int,
    schmelzdichte_kg_m3: float,
    waermekapazitaet_j_kg_k: float,
    waermeleitfaehigkeit_w_m_k: float,
    werkzeugtemperatur_c: float,
    schmelzetemperatur_c: float,
    entformungstemperatur_c: float,
) -> tuple[float, float]:
    """Unabhängige Nachrechnung der IKET-Formel (nicht aus dem Ergebnisobjekt)."""
    alpha = waermeleitfaehigkeit_w_m_k / (schmelzdichte_kg_m3 * waermekapazitaet_j_kg_k)
    faktor = 8.0 / math.pi**2 if variante == 1 else 4.0 / math.pi
    quotient = (schmelzetemperatur_c - werkzeugtemperatur_c) / (
        entformungstemperatur_c - werkzeugtemperatur_c
    )
    t_opt = ((wandstaerke_mm / 1000.0) ** 2 / (alpha * math.pi**2)) * math.log(
        faktor * quotient
    )
    return alpha, t_opt


# --------------------------------------------------------------------------------------
# Formel und POM-Regression
# --------------------------------------------------------------------------------------


def test_temperaturleitfaehigkeit_iket_formel():
    alpha = temperaturleitfaehigkeit(
        waermeleitfaehigkeit_w_m_k=0.27,
        schmelzdichte_kg_m3=783.17,
        waermekapazitaet_j_kg_k=3000.0,
    )
    assert alpha == pytest.approx(0.27 / (783.17 * 3000.0))
    assert alpha == pytest.approx(1.149176e-7, rel=1e-6)


def test_variantenfaktoren_nach_iket():
    assert variantenfaktor(1) == pytest.approx(8.0 / math.pi**2)
    assert variantenfaktor(2) == pytest.approx(4.0 / math.pi)
    assert DEFAULT_VARIANTE == 2


def test_pom_regression_variante_2():
    """Regressionsfall aus der IKET-Datei; Sollwert unabhängig nachgerechnet."""
    result = berechne_zykluszeit(_pom_input())
    alpha_soll, t_opt_soll = _erwartete_kuehlzeit(
        wandstaerke_mm=POM_WANDSTAERKE_MM, variante=2, **POM
    )
    nebenzeiten_soll = sum(DEFAULT_NEBENZEITEN.values())
    gesamt_soll = t_opt_soll * 1.5 + nebenzeiten_soll

    assert result.berechenbar is True
    assert result.hinweis is None
    assert result.temperaturleitfaehigkeit_m2_s == pytest.approx(alpha_soll)
    assert result.temperaturleitfaehigkeit_m2_s == pytest.approx(1.149176e-7, rel=1e-6)
    assert result.temperaturquotient == pytest.approx(4.5)
    assert result.optimale_kuehlzeit_s == pytest.approx(t_opt_soll)
    assert result.optimale_kuehlzeit_s == pytest.approx(31.17, abs=0.01)
    assert result.kuehlzeit_s == pytest.approx(t_opt_soll * 1.5)
    assert nebenzeiten_soll == pytest.approx(12.5)
    assert result.nebenzeiten_gesamt_s == pytest.approx(12.5)
    assert result.gesamtzykluszeit_s == pytest.approx(gesamt_soll)
    assert result.gesamtzykluszeit_s == pytest.approx(59.25, abs=0.01)


def test_kuehlfaktor_default_und_wirkung():
    assert DEFAULT_KUEHLFAKTOR == 1.5
    ohne = berechne_zykluszeit(_pom_input(kuehlfaktor=1.0))
    mit = berechne_zykluszeit(_pom_input(kuehlfaktor=1.5))
    assert mit.optimale_kuehlzeit_s == pytest.approx(ohne.optimale_kuehlzeit_s)
    assert mit.kuehlzeit_s == pytest.approx(ohne.optimale_kuehlzeit_s * 1.5)
    assert mit.gesamtzykluszeit_s == pytest.approx(mit.kuehlzeit_s + 12.5)


def test_variante_1_nutzt_anderen_faktor():
    v1 = berechne_zykluszeit(_pom_input(variante=1))
    _alpha, t_opt_soll = _erwartete_kuehlzeit(
        wandstaerke_mm=POM_WANDSTAERKE_MM, variante=1, **POM
    )
    assert v1.berechenbar is True
    assert v1.variantenfaktor == pytest.approx(8.0 / math.pi**2)
    assert v1.optimale_kuehlzeit_s == pytest.approx(t_opt_soll)


def test_wandstaerke_geht_quadratisch_ein():
    einfach = berechne_zykluszeit(_pom_input(wandstaerke_mm=2.0))
    doppelt = berechne_zykluszeit(_pom_input(wandstaerke_mm=4.0))
    assert doppelt.optimale_kuehlzeit_s == pytest.approx(
        einfach.optimale_kuehlzeit_s * 4
    )


def test_keine_zwischenrundung():
    result = berechne_zykluszeit(_pom_input())
    assert result.gesamtzykluszeit_s == pytest.approx(
        result.kuehlzeit_s + result.nebenzeiten_gesamt_s, rel=0, abs=1e-12
    )
    assert result.gesamtzykluszeit_s != round(result.gesamtzykluszeit_s, 2)


# --------------------------------------------------------------------------------------
# Nebenzeiten
# --------------------------------------------------------------------------------------


def test_nebenzeiten_defaults_entsprechen_iket():
    assert DEFAULT_NEBENZEITEN == {
        "werkzeug_schliessen_s": 2.0,
        "duese_anlegen_s": 1.0,
        "einspritzen_s": 2.0,
        "werkzeug_oeffnen_s": 2.0,
        "auswerfen_s": 2.5,
        "kernzug_s": 1.0,
        "ausschrauben_s": 0.0,
        "einlegen_s": 2.0,
        "ausblasen_s": 0.0,
    }
    assert summe_nebenzeiten(None) == pytest.approx(12.5)


def test_nebenzeiten_summe_und_teilangabe():
    werte = {"einlegen_s": 5.0}
    assert summe_nebenzeiten(werte) == pytest.approx(12.5 - 2.0 + 5.0)
    result = berechne_zykluszeit(_pom_input(nebenzeiten=werte))
    assert result.nebenzeiten["einlegen_s"] == pytest.approx(5.0)
    assert result.nebenzeiten["ausschrauben_s"] == pytest.approx(0.0)
    assert result.nebenzeiten_gesamt_s == pytest.approx(15.5)


def test_nebenzeiten_negativ_wird_abgelehnt():
    result = berechne_zykluszeit(_pom_input(nebenzeiten={"kernzug_s": -1.0}))
    assert result.berechenbar is False
    assert "Nebenzeiten dürfen nicht negativ sein" in result.hinweis


# --------------------------------------------------------------------------------------
# Validierung
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("wandstaerke", [0.0, -1.0])
def test_wandstaerke_muss_positiv_sein(wandstaerke: float):
    result = berechne_zykluszeit(_pom_input(wandstaerke_mm=wandstaerke))
    assert result.berechenbar is False
    assert "Wandstärke" in result.hinweis


def test_fehlende_materialdaten_liefern_hinweis():
    result = berechne_zykluszeit(
        _pom_input(waermeleitfaehigkeit_w_m_k=None, schmelzetemperatur_c=None)
    )
    assert result.berechenbar is False
    assert "Wärmeleitfähigkeit" in result.hinweis
    assert "Schmelzetemperatur" in result.hinweis
    assert result.gesamtzykluszeit_s is None


@pytest.mark.parametrize(
    "feld", ["schmelzdichte_kg_m3", "waermekapazitaet_j_kg_k", "waermeleitfaehigkeit_w_m_k"]
)
def test_division_durch_null_wird_verhindert(feld: str):
    result = berechne_zykluszeit(_pom_input(**{feld: 0.0}))
    assert result.berechenbar is False
    assert "größer als 0" in result.hinweis
    assert result.temperaturleitfaehigkeit_m2_s is None


@pytest.mark.parametrize(
    "temperaturen",
    [
        {"werkzeugtemperatur_c": 90.0},  # Werkzeug > Entformung
        {"entformungstemperatur_c": 250.0},  # Entformung > Schmelze
        {"entformungstemperatur_c": 40.0},  # Entformung == Werkzeug -> Division durch 0
    ],
)
def test_ungueltige_temperaturreihenfolge(temperaturen: dict):
    result = berechne_zykluszeit(_pom_input(**temperaturen))
    assert result.berechenbar is False
    assert "Temperaturreihenfolge" in result.hinweis


def test_ungueltiges_logarithmusargument_variante_1():
    """Variante 1 (Faktor 8/π² < 1) kann bei kleinem Temperaturquotienten kippen."""
    result = berechne_zykluszeit(
        _pom_input(variante=1, entformungstemperatur_c=210.0)
    )
    quotient = (220.0 - 40.0) / (210.0 - 40.0)
    assert 8.0 / math.pi**2 * quotient < 1  # ln < 0 -> negative Kühlzeit
    assert result.berechenbar is False
    assert "Kühlzeit ist nicht positiv" in result.hinweis


def test_kuehlfaktor_muss_positiv_sein():
    result = berechne_zykluszeit(_pom_input(kuehlfaktor=0))
    assert result.berechenbar is False
    assert "Zuschlagfaktor" in result.hinweis


def test_ungueltige_variante():
    result = berechne_zykluszeit(_pom_input(variante=3))
    assert result.berechenbar is False
    assert "Berechnungsvariante" in result.hinweis


def test_mehrkomponenten_liefert_verstaendlichen_hinweis():
    result = berechne_zykluszeit(_pom_input(komponenten=2))
    assert result.berechenbar is False
    assert "1-Komponenten-Spritzguss" in result.hinweis
    assert "Füllstudie" in result.hinweis
    assert result.gesamtzykluszeit_s is None


def test_ein_komponenten_thermoplast_wird_berechnet():
    result = berechne_zykluszeit(_pom_input(komponenten=1))
    assert result.berechenbar is True
    assert result.komponenten == 1


# --------------------------------------------------------------------------------------
# Materialgruppen-Defaults
# --------------------------------------------------------------------------------------


def test_pom_gruppe_entspricht_iket_referenz():
    pom = defaults_fuer_gruppe("POM")
    assert pom is not None
    assert pom.quelle == QUELLE_IKET
    assert pom.thermik_felder() == POM


def test_materialgruppen_defaults_sind_physikalisch_plausibel():
    for gruppe, default in MATERIALGRUPPEN_DEFAULTS.items():
        assert default.schmelzdichte_kg_m3 > 0, gruppe
        assert default.waermekapazitaet_j_kg_k > 0, gruppe
        assert default.waermeleitfaehigkeit_w_m_k > 0, gruppe
        assert (
            default.werkzeugtemperatur_c
            < default.entformungstemperatur_c
            < default.schmelzetemperatur_c
        ), gruppe


def test_materialgruppe_alias_wird_normalisiert():
    assert defaults_fuer_gruppe("pe-hd") is defaults_fuer_gruppe("PEHD")
    assert defaults_fuer_gruppe("unbekannt") is None


def test_material_create_uebernimmt_gruppen_defaults():
    mat = MaterialCreate(
        bezeichnung="Delrin 500P",
        material_nr="POM-1",
        preis_pro_kg="2,10",
        dichte="1,41",
        materialgruppe="pom",
    )
    assert mat.materialgruppe == "POM"
    assert mat.schmelzdichte_kg_m3 == pytest.approx(783.17)
    assert mat.waermekapazitaet_j_kg_k == pytest.approx(3000.0)
    assert mat.entformungstemperatur_c == pytest.approx(80.0)


def test_material_create_eigene_werte_schlagen_defaults():
    mat = MaterialCreate(
        bezeichnung="POM Sonderrezeptur",
        material_nr="POM-2",
        preis_pro_kg=2.0,
        dichte=1.4,
        materialgruppe="POM",
        waermeleitfaehigkeit_w_m_k="0,31",
    )
    assert mat.waermeleitfaehigkeit_w_m_k == pytest.approx(0.31)
    assert mat.schmelzdichte_kg_m3 == pytest.approx(783.17)


def test_material_lehnt_unbekannte_gruppe_ab():
    with pytest.raises(Exception, match="Unbekannte Materialgruppe"):
        MaterialCreate(
            bezeichnung="X",
            material_nr="X-1",
            preis_pro_kg=1,
            dichte=1,
            materialgruppe="XYZ",
        )


def test_material_lehnt_nicht_positive_kennwerte_ab():
    with pytest.raises(Exception, match="größer als 0"):
        MaterialUpdate(waermeleitfaehigkeit_w_m_k=0)


# --------------------------------------------------------------------------------------
# Persistenz und API
# --------------------------------------------------------------------------------------


def _material_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE materialien (
                    id INTEGER PRIMARY KEY,
                    bezeichnung VARCHAR(255) NOT NULL,
                    material_nr VARCHAR(50) NOT NULL UNIQUE,
                    preis_pro_kg FLOAT NOT NULL,
                    dichte FLOAT NOT NULL,
                    waehrung VARCHAR(8) NOT NULL DEFAULT 'EUR',
                    injection_pressure_kg_cm2 FLOAT NOT NULL DEFAULT 500,
                    materialgruppe VARCHAR(32),
                    schmelzdichte_kg_m3 FLOAT,
                    waermekapazitaet_j_kg_k FLOAT,
                    waermeleitfaehigkeit_w_m_k FLOAT,
                    werkzeugtemperatur_c FLOAT,
                    schmelzetemperatur_c FLOAT,
                    entformungstemperatur_c FLOAT,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP
                )
                """
            )
        )


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


def test_thermik_defaults_endpoint(client: TestClient):
    res = client.get(f"{API}/materialien/thermik-defaults")
    assert res.status_code == 200, res.text
    gruppen = {row["gruppe"]: row for row in res.json()}
    assert gruppen["POM"]["schmelzdichte_kg_m3"] == pytest.approx(783.17)
    assert gruppen["POM"]["quelle"] == QUELLE_IKET


def test_material_thermik_speichern_und_laden(client: TestClient, db: Session):
    res = client.post(
        f"{API}/materialien",
        json={
            "bezeichnung": "Delrin 500P NC010",
            "material_nr": "POM-IKET",
            "preis_pro_kg": "2,10",
            "dichte": "1,41",
            "materialgruppe": "POM",
        },
    )
    assert res.status_code == 201, res.text
    body = res.json()
    mid = body["id"]
    assert body["waermeleitfaehigkeit_w_m_k"] == pytest.approx(0.27)

    row = db.query(Material).filter(Material.id == mid).one()
    assert row.schmelzdichte_kg_m3 == pytest.approx(783.17)
    assert row.schmelzetemperatur_c == pytest.approx(220.0)

    upd = client.put(
        f"{API}/materialien/{mid}",
        json={"schmelzetemperatur_c": "215", "waermekapazitaet_j_kg_k": "2950"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["schmelzetemperatur_c"] == pytest.approx(215.0)

    reload = client.get(f"{API}/materialien/{mid}")
    assert reload.json()["waermekapazitaet_j_kg_k"] == pytest.approx(2950.0)
    assert reload.json()["materialgruppe"] == "POM"


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
    body = res.json()
    assert body["materialgruppe"] is None
    assert body["schmelzdichte_kg_m3"] is None


def test_zykluszeit_preview_endpoint_pom(client: TestClient):
    created = client.post(
        f"{API}/materialien",
        json={
            "bezeichnung": "Delrin 500P NC010",
            "material_nr": "POM-PREV",
            "preis_pro_kg": "2,10",
            "dichte": "1,41",
            "materialgruppe": "POM",
        },
    )
    assert created.status_code == 201, created.text
    material_id = created.json()["id"]

    res = client.post(
        f"{API}/spritzguss/zykluszeit/berechnen",
        json={
            "material_id": material_id,
            "zykluszeit_wandstaerke_mm": "4,5",
            "zykluszeit_variante": 2,
            "zykluszeit_kuehlfaktor": "1,5",
            "zykluszeit_komponenten": 1,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    _alpha, t_opt_soll = _erwartete_kuehlzeit(
        wandstaerke_mm=POM_WANDSTAERKE_MM, variante=2, **POM
    )
    assert body["berechenbar"] is True
    assert body["optimale_kuehlzeit_s"] == pytest.approx(t_opt_soll)
    assert body["nebenzeiten_gesamt_s"] == pytest.approx(12.5)
    assert body["gesamtzykluszeit_s"] == pytest.approx(t_opt_soll * 1.5 + 12.5)


def test_zykluszeit_preview_ohne_material_liefert_hinweis(client: TestClient):
    res = client.post(
        f"{API}/spritzguss/zykluszeit/berechnen",
        json={"zykluszeit_wandstaerke_mm": "3,0"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["berechenbar"] is False
    assert "fehlen" in body["hinweis"]


def test_zykluszeit_preview_mehrkomponenten(client: TestClient):
    res = client.post(
        f"{API}/spritzguss/zykluszeit/berechnen",
        json={"zykluszeit_wandstaerke_mm": "3,0", "zykluszeit_komponenten": 2},
    )
    assert res.status_code == 200, res.text
    assert res.json()["berechenbar"] is False
    assert "1-Komponenten-Spritzguss" in res.json()["hinweis"]


def test_zykluszeit_preview_nebenzeiten_wirken(client: TestClient):
    created = client.post(
        f"{API}/materialien",
        json={
            "bezeichnung": "POM",
            "material_nr": "POM-NZ",
            "preis_pro_kg": 2.0,
            "dichte": 1.41,
            "materialgruppe": "POM",
        },
    )
    material_id = created.json()["id"]
    res = client.post(
        f"{API}/spritzguss/zykluszeit/berechnen",
        json={
            "material_id": material_id,
            "zykluszeit_wandstaerke_mm": 4.5,
            "zykluszeit_nz_einlegen_s": "4,5",
            "zykluszeit_nz_ausblasen_s": "1",
        },
    )
    body = res.json()
    assert body["nebenzeiten_gesamt_s"] == pytest.approx(12.5 - 2.0 + 4.5 + 1.0)
    assert body["gesamtzykluszeit_s"] == pytest.approx(
        body["kuehlzeit_s"] + body["nebenzeiten_gesamt_s"]
    )


# --------------------------------------------------------------------------------------
# Schema-Verhalten und Folgewirkung auf Kosten/Kapazität
# --------------------------------------------------------------------------------------


def test_schema_nebenzeiten_dict_faellt_auf_defaults_zurueck():
    fields = ZykluszeitFields(zykluszeit_nz_kernzug_s="2,5")
    werte = fields.nebenzeiten_dict()
    assert set(werte) == set(NEBENZEIT_KEYS)
    assert werte["kernzug_s"] == pytest.approx(2.5)
    assert werte["werkzeug_schliessen_s"] == pytest.approx(2.0)


def test_schema_quelle_nur_manuell_oder_vorschlag():
    assert ZykluszeitFields(zykluszeit_quelle="vorschlag").zykluszeit_quelle == "vorschlag"
    with pytest.raises(Exception, match="manuell"):
        ZykluszeitFields(zykluszeit_quelle="irgendwas")


def test_schema_lehnt_ungueltige_variante_ab():
    with pytest.raises(Exception, match="Berechnungsvariante"):
        ZykluszeitFields(zykluszeit_variante=7)


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
                    zykluszeit_variante INTEGER,
                    zykluszeit_kuehlfaktor FLOAT,
                    zykluszeit_komponenten INTEGER,
                    zykluszeit_nz_werkzeug_schliessen_s FLOAT,
                    zykluszeit_nz_duese_anlegen_s FLOAT,
                    zykluszeit_nz_einspritzen_s FLOAT,
                    zykluszeit_nz_werkzeug_oeffnen_s FLOAT,
                    zykluszeit_nz_auswerfen_s FLOAT,
                    zykluszeit_nz_kernzug_s FLOAT,
                    zykluszeit_nz_ausschrauben_s FLOAT,
                    zykluszeit_nz_einlegen_s FLOAT,
                    zykluszeit_nz_ausblasen_s FLOAT,
                    zykluszeit_temperaturleitfaehigkeit_m2_s FLOAT,
                    zykluszeit_optimale_kuehlzeit_s FLOAT,
                    zykluszeit_kuehlzeit_s FLOAT,
                    zykluszeit_nebenzeiten_gesamt_s FLOAT,
                    zykluszeit_vorschlag_s FLOAT,
                    zykluszeit_hinweis VARCHAR(512)
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
        **POM,
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


def test_zykluszeit_am_datensatz_wird_berechnet_und_gespeichert(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(
        material_id=material.id,
        zykluszeit_wandstaerke_mm=POM_WANDSTAERKE_MM,
        zykluszeit_variante=2,
        zykluszeit_kuehlfaktor=1.5,
        zykluszeit_komponenten=1,
        zykluszeit_quelle="manuell",
    )
    kalk_db.add(obj)
    kalk_db.flush()

    result = _run_zykluszeit_for_model(kalk_db, obj)
    kalk_db.commit()
    assert result is not None and result.berechenbar is True

    _alpha, t_opt_soll = _erwartete_kuehlzeit(
        wandstaerke_mm=POM_WANDSTAERKE_MM, variante=2, **POM
    )
    kalk_db.expire_all()
    geladen = kalk_db.get(SpritzgussKalkulation, obj.id)
    assert geladen.zykluszeit_optimale_kuehlzeit_s == pytest.approx(t_opt_soll)
    assert geladen.zykluszeit_kuehlzeit_s == pytest.approx(t_opt_soll * 1.5)
    assert geladen.zykluszeit_nebenzeiten_gesamt_s == pytest.approx(12.5)
    assert geladen.zykluszeit_vorschlag_s == pytest.approx(t_opt_soll * 1.5 + 12.5)
    assert geladen.zykluszeit_hinweis is None
    # Der Vorschlag überschreibt die bestehende Zykluszeit nicht.
    assert geladen.zykluszeit_s == pytest.approx(30.0)
    assert geladen.zykluszeit_quelle == "manuell"


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


def test_mehrkomponenten_am_datensatz_speichert_hinweis(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(
        material_id=material.id,
        zykluszeit_wandstaerke_mm=3.0,
        zykluszeit_komponenten=2,
    )
    kalk_db.add(obj)
    kalk_db.flush()

    result = _run_zykluszeit_for_model(kalk_db, obj)
    kalk_db.commit()
    assert result.berechenbar is False
    assert obj.zykluszeit_vorschlag_s is None
    assert "1-Komponenten-Spritzguss" in obj.zykluszeit_hinweis


def test_material_ohne_thermik_liefert_hinweis_am_datensatz(kalk_db: Session):
    material = Material(
        bezeichnung="Compound ohne Thermik",
        material_nr="NO-THERM",
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
    assert "fehlen" in obj.zykluszeit_hinweis


def test_export_rows_aus_ergebnis_und_orm(kalk_db: Session):
    material = _pom_material(kalk_db)
    obj = _kalkulation(
        material_id=material.id,
        zykluszeit_wandstaerke_mm=POM_WANDSTAERKE_MM,
        zykluszeit_variante=2,
        zykluszeit_kuehlfaktor=1.5,
        zykluszeit_quelle="vorschlag",
    )
    kalk_db.add(obj)
    kalk_db.flush()
    result = _run_zykluszeit_for_model(kalk_db, obj)

    aus_ergebnis = {
        row.label: row.value
        for row in _zykluszeit_export_rows(obj, {"zykluszeit_vorschlag": result.as_dict()})
    }
    aus_orm = {row.label: row.value for row in _zykluszeit_export_rows(obj, {})}

    assert aus_ergebnis["Zykluszeit Quelle"] == "Übernommen aus Zykluszeitvorschlag"
    assert aus_ergebnis["Äquivalente Wandstärke"] == "4.50 mm"
    assert aus_ergebnis["Kühlzeit-Variante (IKET)"] == "2"
    assert aus_ergebnis["Nebenzeit Auswerfen/Entnahme"] == "2.50 s"
    assert aus_ergebnis["Nebenzeiten gesamt"] == "12.50 s"
    assert aus_ergebnis["Zykluszeit-Vorschlag gesamt"] == "59.25 s"
    # Paritätsprüfung: gespeicherte Spalten liefern dieselben Exportwerte.
    assert aus_orm == aus_ergebnis


def test_export_rows_ohne_vorschlag_zeigen_nur_quelle():
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

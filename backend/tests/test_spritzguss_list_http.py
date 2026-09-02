"""HTTP-Regression: GET /api/v1/spritzguss/ und Detail inkl. Veredelungs-Snapshots."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.core.security import UserRole
from app.database import get_db
from app.dependencies import get_current_user

LIST_URL = "/api/v1/spritzguss/"
DETAIL_URL = "/api/v1/spritzguss/{item_id}"


def _create_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
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
                    losgroesse INTEGER, losgroesse_modus VARCHAR(16), losgroesse_manuell INTEGER,
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
                    werkzeug_abrechnungsart VARCHAR(32) NOT NULL DEFAULT 'einmalzahlung',
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
                    zykluszeit_quelle VARCHAR(16),
                    zykluszeit_wandstaerke_mm FLOAT,
                    zykluszeit_groessenklasse VARCHAR(16),
                    zykluszeit_kuehlzeit_s FLOAT,
                    zykluszeit_nebenzeiten_gesamt_s FLOAT,
                    zykluszeit_vorschlag_s FLOAT,
                    zykluszeit_hinweis VARCHAR(512),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    teilbild_mime VARCHAR(64),
                    teilbild_data TEXT
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE spritzguss_veredelung_zuordnungen (
                    id INTEGER PRIMARY KEY,
                    kalkulation_id INTEGER NOT NULL
                        REFERENCES spritzguss_kalkulationen(id) ON DELETE CASCADE,
                    veredelungsschritt_id INTEGER NOT NULL,
                    reihenfolge INTEGER NOT NULL DEFAULT 1,
                    aktiv BOOLEAN NOT NULL DEFAULT 1,
                    mengenfaktor FLOAT NOT NULL DEFAULT 1,
                    snapshot_bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                    snapshot_veredelungsart VARCHAR(64) NOT NULL DEFAULT '',
                    snapshot_kosten_inkl_ausschuss FLOAT NOT NULL DEFAULT 0,
                    snapshot_kosten_vor_ausschuss FLOAT,
                    snapshot_ausschussquote_pct FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        )


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_schema(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def client(db):
    application = FastAPI()
    application.include_router(api_router)

    def override_get_db():
        yield db

    def override_current_user():
        return SimpleNamespace(
            email="viewer@example.com",
            role=UserRole.VIEWER.value,
            is_active=True,
        )

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_current_user] = override_current_user
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def _insert_kalkulation(
    db,
    *,
    kid: int,
    name: str,
    endpreis: float | None = None,
    customer_id: int | None = None,
    program_id: int | None = None,
    project_id: int | None = None,
    teilbild_mime: str | None = None,
    teilbild_data: str | None = None,
) -> None:
    ergebnis = json.dumps({"endpreis_je_stueck": endpreis}) if endpreis is not None else None
    db.execute(
        text(
            """
            INSERT INTO spritzguss_kalkulationen
            (id, teilebezeichnung, teilenummer, material_nominierung, ergebnis, aktiv,
             customer_id, program_id, project_id, teilbild_mime, teilbild_data)
            VALUES (:id, :name, :nr, 'selbstnominiert', :ergebnis, 1,
                    :customer_id, :program_id, :project_id, :teilbild_mime, :teilbild_data)
            """
        ),
        {
            "id": kid,
            "name": name,
            "nr": f"T-{kid}",
            "ergebnis": ergebnis,
            "customer_id": customer_id,
            "program_id": program_id,
            "project_id": project_id,
            "teilbild_mime": teilbild_mime,
            "teilbild_data": teilbild_data,
        },
    )
    db.commit()


def _insert_zuordnung(
    db,
    *,
    zid: int,
    kid: int,
    vor: float | None,
    quote: float | None,
    inkl: float = 2.03,
) -> None:
    db.execute(
        text(
            """
            INSERT INTO spritzguss_veredelung_zuordnungen
            (id, kalkulation_id, veredelungsschritt_id, reihenfolge, aktiv, mengenfaktor,
             snapshot_bezeichnung, snapshot_veredelungsart, snapshot_kosten_inkl_ausschuss,
             snapshot_kosten_vor_ausschuss, snapshot_ausschussquote_pct)
            VALUES
            (:id, :kid, 10, 1, 1, 1.0, 'Kaschieren TPO', 'Kaschieren', :inkl, :vor, :quote)
            """
        ),
        {"id": zid, "kid": kid, "inkl": inkl, "vor": vor, "quote": quote},
    )
    db.commit()


def test_list_spritzguss_returns_items_with_verkaufspreis(client, db):
    _insert_kalkulation(db, kid=1, name="Armlehne", endpreis=7.37)
    _insert_kalkulation(db, kid=2, name="Grundträger", endpreis=4.20)

    resp = client.get(LIST_URL)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    by_id = {row["id"]: row for row in data}
    assert by_id[1]["teilebezeichnung"] == "Armlehne"
    assert by_id[1]["verkaufspreis"] == pytest.approx(7.37)
    assert by_id[2]["verkaufspreis"] == pytest.approx(4.20)
    assert "teilenummer" in by_id[1]
    assert "aktiv" in by_id[1]


def test_get_kalkulation_legacy_snapshot_ohne_vor_kosten(client, db):
    """Bestehende Zuordnungen vor e1a0007 (NULL Vor-Spalten) müssen ladbar sein."""
    _insert_kalkulation(db, kid=7, name="Armlehne", endpreis=7.37)
    _insert_zuordnung(db, zid=1, kid=7, vor=None, quote=None, inkl=2.03)

    resp = client.get(DETAIL_URL.format(item_id=7))
    assert resp.status_code == 200
    body = resp.json()
    assert body["teilebezeichnung"] == "Armlehne"
    assert body["ergebnis"]["endpreis_je_stueck"] == pytest.approx(7.37)
    assert len(body["veredelung_zuordnungen"]) == 1
    z = body["veredelung_zuordnungen"][0]
    assert z["snapshot_bezeichnung"] == "Kaschieren TPO"
    assert z["snapshot_kosten_inkl_ausschuss"] == pytest.approx(2.03)


def test_get_kalkulation_neue_snapshot_spalten(client, db):
    _insert_kalkulation(db, kid=8, name="Armlehne neu", endpreis=7.37)
    _insert_zuordnung(db, zid=2, kid=8, vor=2.0, quote=1.5, inkl=2.03)

    resp = client.get(DETAIL_URL.format(item_id=8))
    assert resp.status_code == 200
    z = resp.json()["veredelung_zuordnungen"][0]
    assert z["snapshot_kosten_inkl_ausschuss"] == pytest.approx(2.03)
    # Read-Schema exponiert Vor-Spalten nicht; Laden darf trotzdem nicht 500 liefern.
    assert z["snapshot_bezeichnung"] == "Kaschieren TPO"


def test_list_and_detail_ohne_veredelung(client, db):
    _insert_kalkulation(db, kid=9, name="Ohne Veredelung", endpreis=3.5)
    assert client.get(LIST_URL).status_code == 200
    resp = client.get(DETAIL_URL.format(item_id=9))
    assert resp.status_code == 200
    assert resp.json()["veredelung_zuordnungen"] == []


TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_list_returns_teilbild_fields(client, db):
    _insert_kalkulation(
        db,
        kid=10,
        name="Mit Bild",
        endpreis=1.0,
        teilbild_mime="image/png",
        teilbild_data=TINY_PNG_B64,
    )
    row = client.get(LIST_URL).json()[0]
    assert row["teilbild_mime"] == "image/png"
    assert row["teilbild_data"] == TINY_PNG_B64


def test_list_filter_by_hierarchy(client, db):
    _insert_kalkulation(
        db, kid=11, name="K1-P1-Pr1", endpreis=1.0, customer_id=1, program_id=10, project_id=100
    )
    _insert_kalkulation(
        db, kid=12, name="K2-P2-Pr2", endpreis=2.0, customer_id=2, program_id=20, project_id=200
    )

    all_items = client.get(LIST_URL).json()
    assert len(all_items) == 2

    by_customer = client.get(LIST_URL, params={"customer_id": 1}).json()
    assert [row["id"] for row in by_customer] == [11]

    by_program = client.get(LIST_URL, params={"program_id": 20}).json()
    assert [row["id"] for row in by_program] == [12]

    by_project = client.get(LIST_URL, params={"project_id": 100}).json()
    assert [row["id"] for row in by_project] == [11]

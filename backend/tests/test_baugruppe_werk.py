"""Baugruppe werk_id: Persistenz, Filter-Semantik, Export und werkbezogene Markups."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.core.security import UserRole
from app.database import get_db
from app.dependencies import get_current_user
from app.models.baugruppe import Baugruppe
from app.models.land import Land
from app.models.werk import Werk
from app.models.werk_zuschlag import WerkZuschlag
from app.services.baugruppe_export_detail import (
    _resolve_werk,
    build_baugruppe_detail_kalkulation,
)
from app.services.central_markup_rates import load_central_markup_rates

API = "/api/v1"


def _create_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        for stmt in (
            """
            CREATE TABLE laender (
                id INTEGER PRIMARY KEY,
                code VARCHAR(16) NOT NULL UNIQUE,
                name VARCHAR(255) NOT NULL,
                aktiv BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE werke (
                id INTEGER PRIMARY KEY,
                land_id INTEGER NOT NULL REFERENCES laender(id),
                code VARCHAR(32) NOT NULL UNIQUE,
                name VARCHAR(255) NOT NULL,
                currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                fx_to_eur FLOAT NOT NULL DEFAULT 0.92,
                aktiv BOOLEAN NOT NULL DEFAULT 1,
                arbeitstage_pro_jahr FLOAT,
                produktionsintervall_arbeitstage FLOAT,
                schichten_pro_tag FLOAT,
                stunden_pro_schicht FLOAT,
                oee FLOAT,
                space_cost_satz_pro_sqm_jahr FLOAT,
                abschreibungsdauer_jahre FLOAT,
                zinssatz FLOAT,
                versicherungssatz FLOAT,
                instandhaltungssatz FLOAT,
                strompreis FLOAT,
                druckluftpreis FLOAT,
                kuehlwasserpreis FLOAT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE werk_zuschlaege (
                id INTEGER PRIMARY KEY,
                werk_id INTEGER NOT NULL REFERENCES werke(id),
                typ VARCHAR(64) NOT NULL,
                bezeichnung VARCHAR(255) NOT NULL,
                satz_prozent FLOAT NOT NULL,
                kostenbasis VARCHAR(64) NOT NULL DEFAULT '',
                aktiv BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(werk_id, typ)
            )
            """,
            """
            CREATE TABLE zuschlagssaetze (
                id INTEGER PRIMARY KEY,
                typ VARCHAR(64) NOT NULL,
                bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                satz_prozent FLOAT NOT NULL DEFAULT 0,
                aktiv BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE baugruppen (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL DEFAULT '',
                teilenummer VARCHAR(100) NOT NULL DEFAULT '',
                kunde VARCHAR(255) NOT NULL DEFAULT '',
                projekt VARCHAR(255) NOT NULL DEFAULT '',
                jahresstueckzahl INTEGER NOT NULL DEFAULT 0,
                beschreibung TEXT NOT NULL DEFAULT '',
                status VARCHAR(32) NOT NULL DEFAULT 'entwurf',
                aktiv BOOLEAN NOT NULL DEFAULT 1,
                linked_project_id INTEGER,
                project_id INTEGER,
                werk_id INTEGER,
                assembly_type VARCHAR(16) NOT NULL DEFAULT 'TOP_LEVEL',
                structure_version INTEGER NOT NULL DEFAULT 1,
                legacy_mode BOOLEAN NOT NULL DEFAULT 1,
                pricing_status VARCHAR(32) NOT NULL DEFAULT 'NOT_APPLICABLE',
                ergebnis TEXT,
                ergebnis_bloecke TEXT,
                snapshots_captured_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            "CREATE TABLE spritzguss_kalkulationen (id INTEGER PRIMARY KEY)",
            "CREATE TABLE kaufteile (id INTEGER PRIMARY KEY)",
            "CREATE TABLE veredelungsschritte (id INTEGER PRIMARY KEY)",
            """
            CREATE TABLE baugruppe_spritzguss_zuordnungen (
                id INTEGER PRIMARY KEY,
                baugruppe_id INTEGER NOT NULL,
                spritzguss_kalkulation_id INTEGER NOT NULL,
                menge FLOAT NOT NULL DEFAULT 1,
                reihenfolge INTEGER NOT NULL DEFAULT 1,
                snapshot_preis FLOAT NOT NULL DEFAULT 0,
                snapshot_bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                snapshot_teilenummer VARCHAR(100) NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE baugruppe_kaufteil_zuordnungen (
                id INTEGER PRIMARY KEY,
                baugruppe_id INTEGER NOT NULL,
                kaufteil_id INTEGER NOT NULL,
                menge FLOAT NOT NULL DEFAULT 1,
                reihenfolge INTEGER NOT NULL DEFAULT 1,
                snapshot_preis FLOAT NOT NULL DEFAULT 0,
                snapshot_bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                snapshot_lieferant VARCHAR(255) NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE baugruppe_veredelung_zuordnungen (
                id INTEGER PRIMARY KEY,
                baugruppe_id INTEGER NOT NULL,
                veredelungsschritt_id INTEGER NOT NULL,
                reihenfolge INTEGER NOT NULL DEFAULT 1,
                mengenfaktor FLOAT NOT NULL DEFAULT 1,
                snapshot_kosten FLOAT NOT NULL DEFAULT 0,
                snapshot_bezeichnung VARCHAR(255) NOT NULL DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE investitionen (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL DEFAULT '',
                investment_type VARCHAR(64) NOT NULL DEFAULT 'Werkzeug',
                payment_type VARCHAR(64) NOT NULL DEFAULT 'Einmalzahlung',
                amount FLOAT NOT NULL DEFAULT 0,
                cost_amount FLOAT NOT NULL DEFAULT 0,
                bottom_price FLOAT,
                revenue_amount FLOAT,
                amortization_volume INTEGER,
                cost_per_piece FLOAT,
                project_id VARCHAR(255) NOT NULL DEFAULT '',
                customer VARCHAR(255) NOT NULL DEFAULT '',
                part_name VARCHAR(255) NOT NULL DEFAULT '',
                part_number VARCHAR(255) NOT NULL DEFAULT '',
                calculation_id INTEGER,
                baugruppe_id INTEGER,
                supplier VARCHAR(255) NOT NULL DEFAULT '',
                order_date DATE,
                delivery_date DATE,
                status VARCHAR(64) NOT NULL DEFAULT 'In Planung',
                description TEXT NOT NULL DEFAULT '',
                included_in_unit_price BOOLEAN NOT NULL DEFAULT 0,
                archived BOOLEAN NOT NULL DEFAULT 0,
            linked_project_id INTEGER,
            customer_id INTEGER,
            program_id INTEGER,
            assignment_type VARCHAR(32),
            kaufteil_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE assembly_positions (
                id INTEGER PRIMARY KEY,
                parent_assembly_id INTEGER NOT NULL,
                position_type VARCHAR(32) NOT NULL DEFAULT 'PART',
                sequence INTEGER NOT NULL DEFAULT 1,
                quantity FLOAT NOT NULL DEFAULT 1,
                quantity_factor FLOAT NOT NULL DEFAULT 1,
                price_basis VARCHAR(16),
                active BOOLEAN NOT NULL DEFAULT 1,
                label VARCHAR(255),
                part_calculation_id INTEGER,
                purchased_part_id INTEGER,
                child_assembly_id INTEGER,
                finishing_step_id INTEGER,
                cost_snapshot FLOAT,
                price_snapshot FLOAT,
                name_snapshot VARCHAR(255) NOT NULL DEFAULT '',
                part_number_snapshot VARCHAR(100) NOT NULL DEFAULT '',
                supplier_snapshot VARCHAR(255) NOT NULL DEFAULT '',
                snapshots_captured_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ):
            conn.execute(text(stmt))


@pytest.fixture()
def db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    _create_schema(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture()
def client(db: Session):
    application = FastAPI()
    application.include_router(api_router)

    def override_get_db():
        yield db

    def override_current_user():
        return SimpleNamespace(
            email="kalkulator@example.com",
            role=UserRole.KALKULATOR.value,
            is_active=True,
        )

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_current_user] = override_current_user
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def _seed_plants(db: Session) -> tuple[Land, Werk, Werk, Land, Werk]:
    now = datetime.now(timezone.utc)
    sa = Land(code="SA", name="Saudi-Arabien", aktiv=True, created_at=now, updated_at=now)
    de = Land(code="DE", name="Deutschland", aktiv=True, created_at=now, updated_at=now)
    db.add_all([sa, de])
    db.flush()
    kaec = Werk(
        land_id=sa.id,
        code="KAEC",
        name="KAEC",
        currency="USD",
        fx_to_eur=0.92,
        aktiv=True,
        created_at=now,
        updated_at=now,
    )
    old = Werk(
        land_id=sa.id,
        code="OLD",
        name="Altes Werk",
        currency="USD",
        fx_to_eur=0.92,
        aktiv=False,
        created_at=now,
        updated_at=now,
    )
    de_werk = Werk(
        land_id=de.id,
        code="DE1",
        name="Werk DE",
        currency="EUR",
        fx_to_eur=1.0,
        aktiv=True,
        created_at=now,
        updated_at=now,
    )
    db.add_all([kaec, old, de_werk])
    db.flush()
    return sa, kaec, old, de, de_werk


def _seed_central_rates(db: Session) -> None:
    now = datetime.now(timezone.utc)
    for typ, satz in (
        ("mgk_kaufteil_selbst", 3.0),
        ("mgk_kaufteil_oem", 5.0),
        ("fgk", 22.0),
        ("vvgk", 10.0),
        ("gewinn", 15.0),
        ("skonto", 0.0),
    ):
        db.execute(
            text(
                "INSERT INTO zuschlagssaetze (typ, bezeichnung, satz_prozent, aktiv, created_at, updated_at) "
                "VALUES (:t, :t, :s, 1, :c, :u)"
            ),
            {"t": typ, "s": satz, "c": now, "u": now},
        )


def test_create_and_load_baugruppe_with_werk(client: TestClient, db: Session):
    _, kaec, _, _, _ = _seed_plants(db)
    _seed_central_rates(db)
    db.commit()
    resp = client.post(
        f"{API}/baugruppen",
        json={
            "name": "BG KAEC",
            "teilenummer": "BG-1",
            "werk_id": kaec.id,
            "jahresstueckzahl": 0,
            "status": "entwurf",
            "aktiv": True,
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["werk_id"] == kaec.id
    get_resp = client.get(f"{API}/baugruppen/{body['id']}")
    assert get_resp.status_code == 200
    assert get_resp.json()["werk_id"] == kaec.id


def test_werkwechsel_and_legacy_ohne_werk(client: TestClient, db: Session):
    _, kaec, old, _, _ = _seed_plants(db)
    _seed_central_rates(db)
    db.commit()
    created = client.post(
        f"{API}/baugruppen",
        json={"name": "Legacy", "teilenummer": "L-1", "werk_id": None, "aktiv": True},
    ).json()
    assert created["werk_id"] is None
    upd = client.put(
        f"{API}/baugruppen/{created['id']}",
        json={"werk_id": kaec.id, "name": "Legacy"},
    )
    assert upd.status_code == 200, upd.text
    assert upd.json()["werk_id"] == kaec.id
    # Inaktives bestehendes Werk bleibt zuordenbar (bereits gespeichert / bewusst gesetzt)
    upd2 = client.put(
        f"{API}/baugruppen/{created['id']}",
        json={"werk_id": old.id, "name": "Legacy"},
    )
    assert upd2.status_code == 200, upd2.text
    assert upd2.json()["werk_id"] == old.id
    # Zurück auf Legacy ohne Werk
    upd3 = client.put(
        f"{API}/baugruppen/{created['id']}",
        json={"werk_id": None, "name": "Legacy"},
    )
    assert upd3.status_code == 200
    assert upd3.json()["werk_id"] is None


def test_land_werk_filter_api(client: TestClient, db: Session):
    sa, kaec, _, de, de_werk = _seed_plants(db)
    db.commit()
    filtered = client.get(f"{API}/werke?land_id={sa.id}").json()
    assert isinstance(filtered, list), filtered
    assert all(w["land_id"] == sa.id for w in filtered)
    assert any(w["id"] == kaec.id for w in filtered)
    assert all(w["id"] != de_werk.id for w in filtered)
    de_filtered = client.get(f"{API}/werke?land_id={de.id}").json()
    assert all(w["land_id"] == de.id for w in de_filtered)
    assert any(w["id"] == de_werk.id for w in de_filtered)


def test_inactive_werk_still_loadable_on_baugruppe(client: TestClient, db: Session):
    _, _, old, _, _ = _seed_plants(db)
    _seed_central_rates(db)
    db.commit()
    resp = client.post(
        f"{API}/baugruppen",
        json={"name": "Mit inaktiv", "teilenummer": "I-1", "werk_id": old.id, "aktiv": True},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["werk_id"] == old.id
    got = client.get(f"{API}/baugruppen/{resp.json()['id']}")
    assert got.status_code == 200
    assert got.json()["werk_id"] == old.id


def test_resolve_werk_export_labels(db: Session):
    _, kaec, _, _, _ = _seed_plants(db)
    now = datetime.now(timezone.utc)
    bg = Baugruppe(
        name="Export BG",
        teilenummer="E-1",
        werk_id=kaec.id,
        ergebnis={"baugruppenpreis_je_stueck": 1.0, "herstellkosten": 1.0},
        created_at=now,
        updated_at=now,
    )
    db.add(bg)
    db.commit()
    db.refresh(bg)
    land_c, land_n, werk_c, werk_n, wid = _resolve_werk(db, bg)
    assert land_c == "SA"
    assert land_n == "Saudi-Arabien"
    assert werk_c == "KAEC"
    assert werk_n == "KAEC"
    assert wid == kaec.id
    empty = Baugruppe(name="Legacy", werk_id=None, created_at=now, updated_at=now)
    assert _resolve_werk(db, empty) == (None, None, None, None, None)


def test_export_detail_includes_land_and_werk(db: Session):
    _, kaec, _, _, _ = _seed_plants(db)
    _seed_central_rates(db)
    now = datetime.now(timezone.utc)
    bg = Baugruppe(
        name="Export Detail",
        teilenummer="ED-1",
        werk_id=kaec.id,
        jahresstueckzahl=1000,
        ergebnis={
            "baugruppenpreis_je_stueck": 10.0,
            "herstellkosten": 8.0,
            "selbstkosten": 9.0,
            "vvgk": 0.8,
            "gewinn": 1.0,
            "skonto": 0.0,
        },
        created_at=now,
        updated_at=now,
    )
    db.add(bg)
    db.commit()
    db.refresh(bg)
    detail = build_baugruppe_detail_kalkulation(db, bg.id)
    assert detail.land_code == "SA"
    assert detail.land_name == "Saudi-Arabien"
    assert detail.werk_code == "KAEC"
    assert detail.werk_name == "KAEC"
    assert detail.werk_id == kaec.id


def test_werk_handling_override_in_rates(db: Session):
    _, kaec, _, _, _ = _seed_plants(db)
    now = datetime.now(timezone.utc)
    _seed_central_rates(db)
    db.add(
        WerkZuschlag(
            werk_id=kaec.id,
            typ="handling_oem_kaufteil",
            bezeichnung="OEM Handling",
            satz_prozent=6.0,
            kostenbasis="einkaufspreis",
            aktiv=True,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    without = load_central_markup_rates(db, werk_id=None)
    assert without.handling_oem_kaufteil_pct == 0.0
    with_werk = load_central_markup_rates(db, werk_id=kaec.id)
    assert with_werk.handling_oem_kaufteil_pct == pytest.approx(6.0)
    assert with_werk.mgk_kaufteil_oem_pct == pytest.approx(5.0)


def test_baugruppe_calc_uses_werk_markups(client: TestClient, db: Session):
    """Berechnungspfad übergibt werk_id und lädt werkabhängige Zuschläge."""
    _, kaec, _, _, _ = _seed_plants(db)
    now = datetime.now(timezone.utc)
    _seed_central_rates(db)
    db.add(
        WerkZuschlag(
            werk_id=kaec.id,
            typ="vvgk",
            bezeichnung="VVGK Werk",
            satz_prozent=25.0,
            kostenbasis="herstellkosten",
            aktiv=True,
            created_at=now,
            updated_at=now,
        )
    )
    db.commit()
    ohne = client.post(
        f"{API}/baugruppen/berechnen",
        json={
            "name": "Calc",
            "jahresstueckzahl": 1000,
            "werk_id": None,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    mit = client.post(
        f"{API}/baugruppen/berechnen",
        json={
            "name": "Calc",
            "jahresstueckzahl": 1000,
            "werk_id": kaec.id,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert ohne.status_code == 200, ohne.text
    assert mit.status_code == 200, mit.text
    # Ohne Positionen bleibt Endpreis 0, aber werk_id muss akzeptiert werden
    assert mit.json()["ergebnis"]["baugruppenpreis_je_stueck"] == pytest.approx(0.0)
    rates_werk = load_central_markup_rates(db, werk_id=kaec.id)
    rates_ohne = load_central_markup_rates(db, werk_id=None)
    assert rates_werk.vvgk_pct == pytest.approx(25.0)
    assert rates_ohne.vvgk_pct == pytest.approx(10.0)

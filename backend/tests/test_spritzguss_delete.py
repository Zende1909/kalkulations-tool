"""HTTP-Tests: DELETE /api/v1/spritzguss/{id} inkl. Abhängigkeiten."""

from __future__ import annotations

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

DELETE_URL = "/api/v1/spritzguss/{item_id}"
LIST_URL = "/api/v1/spritzguss"


def _create_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        for stmt in (
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
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
            """,
            """
            CREATE TABLE baugruppen (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL DEFAULT '',
                aktiv BOOLEAN NOT NULL DEFAULT 1,
                werk_id INTEGER
            )
            """,
            """
            CREATE TABLE investitionen (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL DEFAULT '',
                investment_type VARCHAR(64) NOT NULL DEFAULT 'Werkzeug',
                payment_type VARCHAR(64) NOT NULL DEFAULT 'Einmalzahlung',
                amount FLOAT NOT NULL DEFAULT 0,
                amortization_volume INTEGER,
                cost_per_piece FLOAT,
                project_id VARCHAR(255) NOT NULL DEFAULT '',
                customer VARCHAR(255) NOT NULL DEFAULT '',
                part_name VARCHAR(255) NOT NULL DEFAULT '',
                part_number VARCHAR(255) NOT NULL DEFAULT '',
                calculation_id INTEGER REFERENCES spritzguss_kalkulationen(id),
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
            CREATE TABLE baugruppe_spritzguss_zuordnungen (
                id INTEGER PRIMARY KEY,
                baugruppe_id INTEGER NOT NULL REFERENCES baugruppen(id),
                spritzguss_kalkulation_id INTEGER NOT NULL
                    REFERENCES spritzguss_kalkulationen(id),
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
            CREATE TABLE assembly_positions (
                id INTEGER PRIMARY KEY,
                parent_assembly_id INTEGER NOT NULL,
                position_type VARCHAR(32) NOT NULL,
                sequence INTEGER NOT NULL DEFAULT 1,
                quantity FLOAT NOT NULL DEFAULT 1,
                quantity_factor FLOAT NOT NULL DEFAULT 1,
                price_basis VARCHAR(32),
                active BOOLEAN NOT NULL DEFAULT 1,
                label VARCHAR(255),
                part_calculation_id INTEGER
                    REFERENCES spritzguss_kalkulationen(id),
                purchased_part_id INTEGER,
                child_assembly_id INTEGER,
                finishing_step_id INTEGER,
                cost_snapshot FLOAT,
                price_snapshot FLOAT,
                name_snapshot VARCHAR(255),
                part_number_snapshot VARCHAR(100),
                supplier_snapshot VARCHAR(255),
                snapshot_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
        ):
            conn.execute(text(stmt))


def _http_app() -> FastAPI:
    application = FastAPI()
    application.include_router(api_router)
    return application


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
    session.execute(text("PRAGMA foreign_keys=ON"))
    yield session
    session.close()


@pytest.fixture()
def client(db):
    application = _http_app()

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


def _insert_kalkulation(db, *, kid: int = 1, teilenummer: str = "T-1") -> None:
    db.execute(
        text(
            """
            INSERT INTO spritzguss_kalkulationen
            (id, teilebezeichnung, teilenummer, material_nominierung)
            VALUES (:id, :name, :nr, 'selbstnominiert')
            """
        ),
        {"id": kid, "name": f"Teil {teilenummer}", "nr": teilenummer},
    )
    db.commit()


def test_delete_ohne_abhaengigkeiten(client, db):
    _insert_kalkulation(db, kid=10, teilenummer="FREE")
    resp = client.delete(DELETE_URL.format(item_id=10))
    assert resp.status_code == 204
    remaining = db.execute(
        text("SELECT count(*) FROM spritzguss_kalkulationen WHERE id = 10")
    ).scalar()
    assert remaining == 0


def test_delete_mit_veredelung_und_investition(client, db):
    _insert_kalkulation(db, kid=20, teilenummer="VERD")
    db.execute(
        text(
            """
            INSERT INTO spritzguss_veredelung_zuordnungen
            (id, kalkulation_id, veredelungsschritt_id, reihenfolge)
            VALUES (1, 20, 99, 1)
            """
        )
    )
    db.execute(
        text(
            """
            INSERT INTO investitionen (id, calculation_id, name, amount)
            VALUES (1, 20, 'Werkzeug', 1000)
            """
        )
    )
    db.commit()

    resp = client.delete(DELETE_URL.format(item_id=20))
    assert resp.status_code == 204
    assert (
        db.execute(
            text("SELECT count(*) FROM spritzguss_kalkulationen WHERE id = 20")
        ).scalar()
        == 0
    )
    assert (
        db.execute(
            text(
                "SELECT count(*) FROM spritzguss_veredelung_zuordnungen "
                "WHERE kalkulation_id = 20"
            )
        ).scalar()
        == 0
    )
    assert (
        db.execute(
            text("SELECT count(*) FROM investitionen WHERE calculation_id = 20")
        ).scalar()
        == 0
    )


def test_delete_blockiert_durch_legacy_baugruppe(client, db):
    _insert_kalkulation(db, kid=30, teilenummer="BG")
    db.execute(text("INSERT INTO baugruppen (id, name) VALUES (1, 'BG-A')"))
    db.execute(
        text(
            """
            INSERT INTO baugruppe_spritzguss_zuordnungen
            (id, baugruppe_id, spritzguss_kalkulation_id, menge, reihenfolge)
            VALUES (1, 1, 30, 1, 1)
            """
        )
    )
    db.commit()

    resp = client.delete(DELETE_URL.format(item_id=30))
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "kann nicht gelöscht" in detail
    assert "Baugruppe" in detail
    assert (
        db.execute(
            text("SELECT count(*) FROM spritzguss_kalkulationen WHERE id = 30")
        ).scalar()
        == 1
    )


def test_delete_blockiert_durch_assembly_position(client, db):
    _insert_kalkulation(db, kid=40, teilenummer="AP")
    db.execute(
        text(
            """
            INSERT INTO assembly_positions
            (id, parent_assembly_id, position_type, sequence, part_calculation_id)
            VALUES (1, 7, 'PART', 1, 40)
            """
        )
    )
    db.commit()

    resp = client.delete(DELETE_URL.format(item_id=40))
    assert resp.status_code == 409
    detail = resp.json()["detail"]
    assert "Baugruppen-Position" in detail or "assembly_positions" in detail
    assert (
        db.execute(
            text("SELECT count(*) FROM spritzguss_kalkulationen WHERE id = 40")
        ).scalar()
        == 1
    )


def test_delete_entfernt_aus_liste(client, db):
    _insert_kalkulation(db, kid=50, teilenummer="LIST")
    _insert_kalkulation(db, kid=51, teilenummer="KEEP")
    before = client.get(LIST_URL)
    assert before.status_code == 200
    ids_before = {row["id"] for row in before.json()}
    assert 50 in ids_before and 51 in ids_before

    resp = client.delete(DELETE_URL.format(item_id=50))
    assert resp.status_code == 204

    after = client.get(LIST_URL)
    assert after.status_code == 200
    ids_after = {row["id"] for row in after.json()}
    assert 50 not in ids_after
    assert 51 in ids_after


def test_delete_nicht_gefunden(client):
    resp = client.delete(DELETE_URL.format(item_id=9999))
    assert resp.status_code == 404
    assert "nicht gefunden" in resp.json()["detail"]

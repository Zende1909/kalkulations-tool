"""HTTP-Tests: Baugruppe archivieren/löschen und Listenfilter."""

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

LIST_URL = "/api/v1/baugruppen"
ARCHIVE_URL = "/api/v1/baugruppen/{item_id}/archivieren"
DELETE_URL = "/api/v1/baugruppen/{item_id}"


def _create_schema(engine) -> None:
    with engine.begin() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        for stmt in (
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
                    zykluszeit_hinweis VARCHAR(512),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """,
            """
            CREATE TABLE baugruppe_spritzguss_zuordnungen (
                id INTEGER PRIMARY KEY,
                baugruppe_id INTEGER NOT NULL REFERENCES baugruppen(id) ON DELETE CASCADE,
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
            CREATE TABLE baugruppe_kaufteil_zuordnungen (
                id INTEGER PRIMARY KEY,
                baugruppe_id INTEGER NOT NULL REFERENCES baugruppen(id) ON DELETE CASCADE,
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
                baugruppe_id INTEGER NOT NULL REFERENCES baugruppen(id) ON DELETE CASCADE,
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
            CREATE TABLE assembly_positions (
                id INTEGER PRIMARY KEY,
                parent_assembly_id INTEGER NOT NULL REFERENCES baugruppen(id) ON DELETE CASCADE,
                position_type VARCHAR(32) NOT NULL,
                sequence INTEGER NOT NULL DEFAULT 1,
                quantity FLOAT NOT NULL DEFAULT 1,
                quantity_factor FLOAT NOT NULL DEFAULT 1,
                price_basis VARCHAR(32),
                active BOOLEAN NOT NULL DEFAULT 1,
                label VARCHAR(255),
                part_calculation_id INTEGER REFERENCES spritzguss_kalkulationen(id),
                purchased_part_id INTEGER,
                child_assembly_id INTEGER REFERENCES baugruppen(id),
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
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    session.execute(text("PRAGMA foreign_keys=ON"))
    session.execute(
        text(
            """
            INSERT INTO zuschlagssaetze (typ, bezeichnung, satz_prozent, aktiv) VALUES
            ('mgk_kaufteil_selbst', 'MGK', 3, 1),
            ('mgk_kaufteil_oem', 'MGK OEM', 5, 1),
            ('fgk', 'FGK', 22, 1),
            ('vvgk', 'VVGK', 10, 1),
            ('gewinn', 'Gewinn', 15, 1),
            ('skonto', 'Skonto', 0, 1)
            """
        )
    )
    session.commit()
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
            email="kalkulator@example.com",
            role=UserRole.KALKULATOR.value,
            is_active=True,
        )

    application.dependency_overrides[get_db] = override_get_db
    application.dependency_overrides[get_current_user] = override_current_user
    with TestClient(application) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def _insert_bg(db, *, bg_id: int, name: str = "BG", aktiv: bool = True) -> None:
    db.execute(
        text(
            """
            INSERT INTO baugruppen (id, name, status, aktiv)
            VALUES (:id, :name, :status, :aktiv)
            """
        ),
        {
            "id": bg_id,
            "name": name,
            "status": "aktiv" if aktiv else "archiviert",
            "aktiv": 1 if aktiv else 0,
        },
    )
    db.commit()


def _insert_sg(db, *, kid: int) -> None:
    db.execute(
        text(
            """
            INSERT INTO spritzguss_kalkulationen (id, teilebezeichnung, teilenummer)
            VALUES (:id, :name, :nr)
            """
        ),
        {"id": kid, "name": f"Teil {kid}", "nr": f"T-{kid}"},
    )
    db.commit()


def test_list_aktive_und_archivierte(client, db):
    _insert_bg(db, bg_id=1, name="Aktiv-BG", aktiv=True)
    _insert_bg(db, bg_id=2, name="Archiv-BG", aktiv=False)

    active = client.get(LIST_URL, params={"aktiv": "true"})
    assert active.status_code == 200
    assert {r["id"] for r in active.json()} == {1}

    archived = client.get(LIST_URL, params={"aktiv": "false"})
    assert archived.status_code == 200
    assert {r["id"] for r in archived.json()} == {2}

    all_rows = client.get(LIST_URL)
    assert {r["id"] for r in all_rows.json()} == {1, 2}


def test_archivieren_behaelt_datensatz(client, db):
    _insert_bg(db, bg_id=10, name="ToArchive", aktiv=True)
    resp = client.post(ARCHIVE_URL.format(item_id=10))
    assert resp.status_code == 204
    row = db.execute(text("SELECT aktiv, status FROM baugruppen WHERE id = 10")).one()
    assert row[0] in (0, False)
    assert row[1] == "archiviert"


def test_get_archiviert_ohne_reaktivierung(client, db):
    _insert_bg(db, bg_id=11, name="ArchivedOpen", aktiv=False)
    resp = client.get(f"{LIST_URL}/11")
    assert resp.status_code == 200
    body = resp.json()
    assert body["aktiv"] is False
    assert body["status"] == "archiviert"
    # GET ändert nichts
    row = db.execute(text("SELECT aktiv, status FROM baugruppen WHERE id = 11")).one()
    assert row[0] in (0, False)
    assert row[1] == "archiviert"


def test_update_ohne_status_laesst_archiviert(client, db):
    _insert_bg(db, bg_id=12, name="StayArchived", aktiv=False)
    resp = client.put(
        f"{LIST_URL}/12",
        json={"name": "StayArchived-updated", "beschreibung": "nur Inhalt"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "StayArchived-updated"
    assert body["aktiv"] is False
    assert body["status"] == "archiviert"


def test_reaktivierung_via_status_aktiv(client, db):
    _insert_bg(db, bg_id=13, name="ReactivateMe", aktiv=False)
    resp = client.put(f"{LIST_URL}/13", json={"status": "aktiv"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["aktiv"] is True
    assert body["status"] == "aktiv"
    row = db.execute(text("SELECT aktiv, status FROM baugruppen WHERE id = 13")).one()
    assert row[0] in (1, True)
    assert row[1] == "aktiv"


def test_erneutes_archivieren_nach_reaktivierung(client, db):
    _insert_bg(db, bg_id=14, name="Cycle", aktiv=False)
    assert client.put(f"{LIST_URL}/14", json={"status": "aktiv"}).status_code == 200
    assert client.post(ARCHIVE_URL.format(item_id=14)).status_code == 204
    row = db.execute(text("SELECT aktiv, status FROM baugruppen WHERE id = 14")).one()
    assert row[0] in (0, False)
    assert row[1] == "archiviert"


def test_delete_ohne_positionen(client, db):
    _insert_bg(db, bg_id=20, name="Empty")
    resp = client.delete(DELETE_URL.format(item_id=20))
    assert resp.status_code == 204
    assert (
        db.execute(text("SELECT count(*) FROM baugruppen WHERE id = 20")).scalar() == 0
    )


def test_delete_mit_eigenen_positionen_und_legacy(client, db):
    _insert_bg(db, bg_id=30, name="WithPos")
    _insert_sg(db, kid=100)
    db.execute(
        text(
            """
            INSERT INTO assembly_positions
            (id, parent_assembly_id, position_type, sequence, part_calculation_id)
            VALUES (1, 30, 'PART', 1, 100)
            """
        )
    )
    db.execute(
        text(
            """
            INSERT INTO baugruppe_spritzguss_zuordnungen
            (id, baugruppe_id, spritzguss_kalkulation_id, menge, reihenfolge)
            VALUES (1, 30, 100, 1, 1)
            """
        )
    )
    db.commit()

    resp = client.delete(DELETE_URL.format(item_id=30))
    assert resp.status_code == 204
    assert db.execute(text("SELECT count(*) FROM baugruppen WHERE id = 30")).scalar() == 0
    assert (
        db.execute(
            text("SELECT count(*) FROM assembly_positions WHERE parent_assembly_id = 30")
        ).scalar()
        == 0
    )
    assert (
        db.execute(
            text(
                "SELECT count(*) FROM baugruppe_spritzguss_zuordnungen "
                "WHERE baugruppe_id = 30"
            )
        ).scalar()
        == 0
    )
    # Spritzguss bleibt bestehen
    assert (
        db.execute(text("SELECT count(*) FROM spritzguss_kalkulationen WHERE id = 100")).scalar()
        == 1
    )


def test_delete_blockiert_wenn_als_unterbaugruppe_verwendet(client, db):
    _insert_bg(db, bg_id=40, name="Child")
    _insert_bg(db, bg_id=41, name="Parent")
    db.execute(
        text(
            """
            INSERT INTO assembly_positions
            (id, parent_assembly_id, position_type, sequence, child_assembly_id, price_basis)
            VALUES (1, 41, 'SUBASSEMBLY', 1, 40, 'COST')
            """
        )
    )
    db.commit()

    resp = client.delete(DELETE_URL.format(item_id=40))
    assert resp.status_code == 409
    assert "Unterbaugruppe" in resp.json()["detail"]
    assert db.execute(text("SELECT count(*) FROM baugruppen WHERE id = 40")).scalar() == 1


def test_spritzguss_delete_blockiert_aktive_baugruppe(client, db):
    _insert_bg(db, bg_id=50, name="ActiveRef", aktiv=True)
    _insert_sg(db, kid=200)
    db.execute(
        text(
            """
            INSERT INTO baugruppe_spritzguss_zuordnungen
            (id, baugruppe_id, spritzguss_kalkulation_id)
            VALUES (1, 50, 200)
            """
        )
    )
    db.commit()
    resp = client.delete("/api/v1/spritzguss/200")
    assert resp.status_code == 409
    assert "archiviert" in resp.json()["detail"] or "Baugruppen" in resp.json()["detail"]


def test_spritzguss_delete_blockiert_archivierte_baugruppe(client, db):
    _insert_bg(db, bg_id=51, name="ArchivedRef", aktiv=False)
    _insert_sg(db, kid=201)
    db.execute(
        text(
            """
            INSERT INTO assembly_positions
            (id, parent_assembly_id, position_type, sequence, part_calculation_id)
            VALUES (1, 51, 'PART', 1, 201)
            """
        )
    )
    db.commit()
    resp = client.delete("/api/v1/spritzguss/201")
    assert resp.status_code == 409
    assert db.execute(text("SELECT count(*) FROM spritzguss_kalkulationen WHERE id = 201")).scalar() == 1


def test_spritzguss_delete_ohne_verwendung(client, db):
    _insert_sg(db, kid=202)
    resp = client.delete("/api/v1/spritzguss/202")
    assert resp.status_code == 204
    assert (
        db.execute(text("SELECT count(*) FROM spritzguss_kalkulationen WHERE id = 202")).scalar()
        == 0
    )

"""Baugruppe project_id-Hierarchie und Projekte-Filter nach Kunde."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.router import api_router
from app.api.v1.baugruppen import (
    _apply_project_to_baugruppe_payload,
    _resolve_customer_id_for_project,
)
from app.core.security import UserRole
from app.database import get_db
from app.dependencies import get_current_user
from app.models.baugruppe import Baugruppe
from app.models.customer import Customer
from app.models.program import Program
from app.models.project import Project


def _create_schema(engine) -> None:
    statements = [
        """
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            customer_number VARCHAR(50) NOT NULL,
            name VARCHAR(255) NOT NULL,
            notes TEXT NOT NULL DEFAULT '',
            active BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS programs (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER NOT NULL REFERENCES customers(id),
            program_number VARCHAR(50) NOT NULL,
            name VARCHAR(255) NOT NULL,
            vehicle_series VARCHAR(255) NOT NULL DEFAULT '',
            sop DATE,
            eop DATE,
            status VARCHAR(32) NOT NULL DEFAULT 'Anfrage',
            production_plant VARCHAR(255) NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            active BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY,
            program_id INTEGER NOT NULL REFERENCES programs(id),
            project_number VARCHAR(50) NOT NULL,
            name VARCHAR(255) NOT NULL,
            component_area VARCHAR(255) NOT NULL DEFAULT '',
            quantity_per_vehicle FLOAT NOT NULL DEFAULT 1,
            status VARCHAR(32) NOT NULL DEFAULT 'Anfrage',
            notes TEXT NOT NULL DEFAULT '',
            active BOOLEAN NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS baugruppen (
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
            project_id INTEGER REFERENCES projects(id),
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
        "CREATE TABLE IF NOT EXISTS spritzguss_kalkulationen (id INTEGER PRIMARY KEY)",
        "CREATE TABLE IF NOT EXISTS kaufteile (id INTEGER PRIMARY KEY)",
        "CREATE TABLE IF NOT EXISTS veredelungsschritte (id INTEGER PRIMARY KEY)",
        """
        CREATE TABLE IF NOT EXISTS baugruppe_spritzguss_zuordnungen (
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
        CREATE TABLE IF NOT EXISTS baugruppe_kaufteil_zuordnungen (
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
        CREATE TABLE IF NOT EXISTS baugruppe_veredelung_zuordnungen (
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
        CREATE TABLE IF NOT EXISTS investitionen (
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
    ]
    with engine.begin() as conn:
        for stmt in statements:
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


@pytest.fixture()
def hierarchy(db: Session) -> dict[str, int]:
    c1 = Customer(customer_number="C-1", name="Kunde Alpha", notes="", active=True)
    c2 = Customer(customer_number="C-2", name="Kunde Beta", notes="", active=True)
    db.add_all([c1, c2])
    db.flush()
    p1 = Program(
        customer_id=c1.id,
        program_number="P-1",
        name="Programm Alpha",
        vehicle_series="X",
        sop=date(2024, 1, 1),
        eop=date(2028, 12, 31),
        status="Laufend",
        production_plant="",
        notes="",
        active=True,
    )
    p2 = Program(
        customer_id=c2.id,
        program_number="P-2",
        name="Programm Beta",
        vehicle_series="Y",
        sop=date(2024, 1, 1),
        eop=date(2028, 12, 31),
        status="Laufend",
        production_plant="",
        notes="",
        active=True,
    )
    db.add_all([p1, p2])
    db.flush()
    pr1 = Project(
        program_id=p1.id,
        project_number="PRJ-1",
        name="Projekt Alpha",
        component_area="Interior",
        quantity_per_vehicle=1,
        status="Laufend",
        notes="",
        active=True,
    )
    pr2 = Project(
        program_id=p2.id,
        project_number="PRJ-2",
        name="Projekt Beta",
        component_area="Exterior",
        quantity_per_vehicle=1,
        status="Laufend",
        notes="",
        active=True,
    )
    db.add_all([pr1, pr2])
    db.commit()
    return {
        "customer_1": c1.id,
        "customer_2": c2.id,
        "project_1": pr1.id,
        "project_2": pr2.id,
    }


def test_apply_project_payload_denormalizes_kunde_projekt(db: Session, hierarchy: dict[str, int]):
    payload = _apply_project_to_baugruppe_payload(
        db, {"name": "BG", "project_id": hierarchy["project_1"]}
    )
    assert payload["kunde"] == "Kunde Alpha"
    assert payload["projekt"] == "Projekt Alpha"
    assert payload["linked_project_id"] == hierarchy["project_1"]
    assert _resolve_customer_id_for_project(db, hierarchy["project_1"]) == hierarchy["customer_1"]


def test_apply_project_payload_rejects_unknown_project(db: Session):
    with pytest.raises(Exception) as exc:
        _apply_project_to_baugruppe_payload(db, {"project_id": 999_999})
    assert getattr(exc.value, "status_code", None) == 422


def test_list_projects_filter_by_customer_id(client: TestClient, hierarchy: dict[str, int]):
    r = client.get(f"/api/v1/projects?customer_id={hierarchy['customer_1']}&active=true")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == hierarchy["project_1"]
    assert rows[0]["name"] == "Projekt Alpha"


def test_create_baugruppe_with_project_id_sets_kunde_projekt(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    payload = {
        "name": "BG Hierarchy",
        "teilenummer": "BG-H-1",
        "project_id": hierarchy["project_1"],
        "jahresstueckzahl": 1000,
        "status": "entwurf",
        "aktiv": True,
        "spritzguss_zuordnungen": [],
        "kaufteil_zuordnungen": [],
        "veredelung_zuordnungen": [],
    }
    r = client.post("/api/v1/baugruppen", json=payload)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["project_id"] == hierarchy["project_1"]
    assert body["customer_id"] == hierarchy["customer_1"]
    assert body["kunde"] == "Kunde Alpha"
    assert body["projekt"] == "Projekt Alpha"

    row = db.get(Baugruppe, body["id"])
    assert row is not None
    assert row.project_id == hierarchy["project_1"]
    assert row.linked_project_id == hierarchy["project_1"]


def test_create_baugruppe_invalid_project_id(client: TestClient):
    payload = {
        "name": "BG Bad",
        "project_id": 999_999,
        "jahresstueckzahl": 0,
        "spritzguss_zuordnungen": [],
        "kaufteil_zuordnungen": [],
        "veredelung_zuordnungen": [],
    }
    r = client.post("/api/v1/baugruppen", json=payload)
    assert r.status_code == 422


def test_update_baugruppe_changes_project(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    create = client.post(
        "/api/v1/baugruppen",
        json={
            "name": "BG Switch",
            "project_id": hierarchy["project_1"],
            "jahresstueckzahl": 10,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert create.status_code == 201, create.text
    bg_id = create.json()["id"]

    upd = client.put(
        f"/api/v1/baugruppen/{bg_id}",
        json={"project_id": hierarchy["project_2"]},
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["project_id"] == hierarchy["project_2"]
    assert body["customer_id"] == hierarchy["customer_2"]
    assert body["kunde"] == "Kunde Beta"
    assert body["projekt"] == "Projekt Beta"

    row = db.get(Baugruppe, bg_id)
    assert row is not None
    assert row.project_id == hierarchy["project_2"]


def test_update_legacy_baugruppe_without_project_id_keeps_freitext(
    client: TestClient, db: Session
):
    create = client.post(
        "/api/v1/baugruppen",
        json={
            "name": "BG Legacy",
            "kunde": "Freitext-Kunde",
            "projekt": "Freitext-Projekt",
            "jahresstueckzahl": 5,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert create.status_code == 201, create.text
    bg_id = create.json()["id"]
    assert create.json()["project_id"] is None

    upd = client.put(
        f"/api/v1/baugruppen/{bg_id}",
        json={
            "name": "BG Legacy geändert",
            "kunde": "Freitext-Kunde",
            "projekt": "Freitext-Projekt",
            "jahresstueckzahl": 7,
        },
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["name"] == "BG Legacy geändert"
    assert body["kunde"] == "Freitext-Kunde"
    assert body["projekt"] == "Freitext-Projekt"
    assert body["project_id"] is None
    assert body["jahresstueckzahl"] == 7

    row = db.get(Baugruppe, bg_id)
    assert row is not None
    assert row.project_id is None
    assert row.kunde == "Freitext-Kunde"
    assert row.projekt == "Freitext-Projekt"


def test_update_null_project_id_preserves_existing_linked_project_id(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    """project_id=null im Payload darf linked_project_id nicht löschen, wenn project_id schon null war."""
    create = client.post(
        "/api/v1/baugruppen",
        json={
            "name": "BG Linked Legacy",
            "kunde": "Alt-Kunde",
            "projekt": "Alt-Projekt",
            "jahresstueckzahl": 3,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert create.status_code == 201, create.text
    bg_id = create.json()["id"]

    row = db.get(Baugruppe, bg_id)
    assert row is not None
    row.linked_project_id = hierarchy["project_1"]
    row.project_id = None
    db.add(row)
    db.commit()

    upd = client.put(
        f"/api/v1/baugruppen/{bg_id}",
        json={
            "name": "BG Linked Legacy 2",
            "project_id": None,
            "kunde": "Alt-Kunde",
            "projekt": "Alt-Projekt",
            "jahresstueckzahl": 4,
        },
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["name"] == "BG Linked Legacy 2"
    # Read leitet project_id/customer_id aus linked_project_id ab
    assert body["project_id"] == hierarchy["project_1"]
    assert body["customer_id"] == hierarchy["customer_1"]
    assert body["kunde"] == "Alt-Kunde"
    assert body["projekt"] == "Alt-Projekt"

    refreshed = db.get(Baugruppe, bg_id)
    assert refreshed is not None
    assert refreshed.project_id is None
    assert refreshed.linked_project_id == hierarchy["project_1"]


def test_get_baugruppe_derives_hierarchy_from_linked_project_id(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    create = client.post(
        "/api/v1/baugruppen",
        json={
            "name": "BG Linked Only",
            "kunde": "Alt",
            "projekt": "AltP",
            "jahresstueckzahl": 1,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert create.status_code == 201, create.text
    bg_id = create.json()["id"]
    row = db.get(Baugruppe, bg_id)
    assert row is not None
    row.project_id = None
    row.linked_project_id = hierarchy["project_1"]
    db.add(row)
    db.commit()

    got = client.get(f"/api/v1/baugruppen/{bg_id}")
    assert got.status_code == 200, got.text
    body = got.json()
    assert body["project_id"] == hierarchy["project_1"]
    assert body["customer_id"] == hierarchy["customer_1"]


def test_update_explicit_clear_project_link_clears_both_ids(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    create = client.post(
        "/api/v1/baugruppen",
        json={
            "name": "BG Unlink",
            "project_id": hierarchy["project_1"],
            "jahresstueckzahl": 1,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert create.status_code == 201, create.text
    bg_id = create.json()["id"]

    upd = client.put(
        f"/api/v1/baugruppen/{bg_id}",
        json={"clear_project_link": True, "name": "BG Unlinked"},
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["project_id"] is None
    assert body["customer_id"] is None

    row = db.get(Baugruppe, bg_id)
    assert row is not None
    assert row.project_id is None
    assert row.linked_project_id is None


def test_update_clear_project_link_on_linked_only_clears_both(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    create = client.post(
        "/api/v1/baugruppen",
        json={
            "name": "BG Linked Unlink",
            "kunde": "Alt",
            "projekt": "AltP",
            "jahresstueckzahl": 1,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert create.status_code == 201, create.text
    bg_id = create.json()["id"]
    row = db.get(Baugruppe, bg_id)
    assert row is not None
    row.project_id = None
    row.linked_project_id = hierarchy["project_1"]
    db.add(row)
    db.commit()

    upd = client.put(
        f"/api/v1/baugruppen/{bg_id}",
        json={"clear_project_link": True, "project_id": None, "name": "BG Linked Unlinked"},
    )
    assert upd.status_code == 200, upd.text
    refreshed = db.get(Baugruppe, bg_id)
    assert refreshed is not None
    assert refreshed.project_id is None
    assert refreshed.linked_project_id is None


def test_update_linked_only_keeps_link_on_normal_save(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    create = client.post(
        "/api/v1/baugruppen",
        json={
            "name": "BG Linked Keep",
            "kunde": "Alt",
            "projekt": "AltP",
            "jahresstueckzahl": 1,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert create.status_code == 201, create.text
    bg_id = create.json()["id"]
    row = db.get(Baugruppe, bg_id)
    assert row is not None
    row.project_id = None
    row.linked_project_id = hierarchy["project_1"]
    db.add(row)
    db.commit()

    upd = client.put(
        f"/api/v1/baugruppen/{bg_id}",
        json={
            "name": "BG Linked Keep 2",
            "project_id": hierarchy["project_1"],
            "jahresstueckzahl": 2,
        },
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["project_id"] == hierarchy["project_1"]
    assert body["customer_id"] == hierarchy["customer_1"]
    refreshed = db.get(Baugruppe, bg_id)
    assert refreshed is not None
    assert refreshed.project_id == hierarchy["project_1"]
    assert refreshed.linked_project_id == hierarchy["project_1"]


def test_update_linked_only_inactive_project_allows_normal_save(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    create = client.post(
        "/api/v1/baugruppen",
        json={
            "name": "BG Linked Inactive",
            "kunde": "Alt",
            "projekt": "AltP",
            "jahresstueckzahl": 1,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert create.status_code == 201, create.text
    bg_id = create.json()["id"]
    row = db.get(Baugruppe, bg_id)
    assert row is not None
    row.project_id = None
    row.linked_project_id = hierarchy["project_1"]
    db.add(row)
    project = db.get(Project, hierarchy["project_1"])
    assert project is not None
    project.active = False
    db.add(project)
    db.commit()

    upd = client.put(
        f"/api/v1/baugruppen/{bg_id}",
        json={
            "name": "BG Linked Inactive 2",
            "project_id": hierarchy["project_1"],
            "jahresstueckzahl": 3,
        },
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["name"] == "BG Linked Inactive 2"
    assert body["project_id"] == hierarchy["project_1"]
    refreshed = db.get(Baugruppe, bg_id)
    assert refreshed is not None
    assert refreshed.linked_project_id == hierarchy["project_1"]


def test_update_keeps_existing_inactive_project_id(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    create = client.post(
        "/api/v1/baugruppen",
        json={
            "name": "BG Inactive Keep",
            "project_id": hierarchy["project_1"],
            "jahresstueckzahl": 1,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert create.status_code == 201, create.text
    bg_id = create.json()["id"]

    project = db.get(Project, hierarchy["project_1"])
    assert project is not None
    project.active = False
    db.add(project)
    db.commit()

    upd = client.put(
        f"/api/v1/baugruppen/{bg_id}",
        json={
            "name": "BG Inactive Keep 2",
            "project_id": hierarchy["project_1"],
            "jahresstueckzahl": 2,
        },
    )
    assert upd.status_code == 200, upd.text
    body = upd.json()
    assert body["name"] == "BG Inactive Keep 2"
    assert body["project_id"] == hierarchy["project_1"]
    assert body["customer_id"] == hierarchy["customer_1"]
    assert body["kunde"] == "Kunde Alpha"
    assert body["projekt"] == "Projekt Alpha"


def test_update_rejects_switch_to_inactive_project_id(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    create = client.post(
        "/api/v1/baugruppen",
        json={
            "name": "BG Switch Inactive",
            "project_id": hierarchy["project_1"],
            "jahresstueckzahl": 1,
            "spritzguss_zuordnungen": [],
            "kaufteil_zuordnungen": [],
            "veredelung_zuordnungen": [],
        },
    )
    assert create.status_code == 201, create.text
    bg_id = create.json()["id"]

    project = db.get(Project, hierarchy["project_2"])
    assert project is not None
    project.active = False
    db.add(project)
    db.commit()

    upd = client.put(
        f"/api/v1/baugruppen/{bg_id}",
        json={"project_id": hierarchy["project_2"]},
    )
    assert upd.status_code == 422


def test_list_projects_active_filter_excludes_inactive(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    project = db.get(Project, hierarchy["project_1"])
    assert project is not None
    project.active = False
    db.add(project)
    db.commit()

    active = client.get(f"/api/v1/projects?customer_id={hierarchy['customer_1']}&active=true")
    assert active.status_code == 200
    assert active.json() == []

    all_rows = client.get(f"/api/v1/projects?customer_id={hierarchy['customer_1']}")
    assert all_rows.status_code == 200
    assert len(all_rows.json()) == 1
    assert all_rows.json()[0]["id"] == hierarchy["project_1"]
    assert all_rows.json()[0]["active"] is False


def test_get_inactive_customer_and_project_for_edit_form(
    client: TestClient, db: Session, hierarchy: dict[str, int]
):
    customer = db.get(Customer, hierarchy["customer_1"])
    project = db.get(Project, hierarchy["project_1"])
    assert customer is not None and project is not None
    customer.active = False
    project.active = False
    db.add_all([customer, project])
    db.commit()

    c = client.get(f"/api/v1/customers/{hierarchy['customer_1']}")
    p = client.get(f"/api/v1/projects/{hierarchy['project_1']}")
    assert c.status_code == 200
    assert p.status_code == 200
    assert c.json()["active"] is False
    assert p.json()["active"] is False
    assert c.json()["name"] == "Kunde Alpha"
    assert p.json()["name"] == "Projekt Alpha"

"""HTTP-Integrationstests für POST /baugruppen/{id}/recalculate."""

from __future__ import annotations

from datetime import UTC, datetime
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
from app.models.assembly_position import AssemblyPosition
from app.schemas.assembly_structure import AssemblyPositionInput
from tests.test_assembly_calculation_phase_c import (
    _create_phase_c_schema,
    _part_pos,
    _put,
    _seed_markups,
    _seed_project,
    _seed_references,
    _top,
)

RECALCULATE_URL = "/api/v1/baugruppen/{baugruppe_id}/recalculate"


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
    _create_phase_c_schema(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
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


def _seed_structure_with_part_snapshot(db):
    _seed_project(db)
    _seed_references(db)
    top = _top(db)
    _put(db, top.id, [_part_pos()])
    pos = db.query(AssemblyPosition).one()
    pos.cost_snapshot = 4.2
    pos.snapshots_captured_at = datetime.now(UTC)
    db.commit()
    return top


def _seed_markups_except(db, missing_typ: str) -> None:
    rates = [
        (1, "VVGK", 0.0, "vvgk"),
        (2, "Gewinn", 0.0, "gewinn"),
        (3, "Skonto", 0.0, "skonto"),
        (4, "FGK", 22.0, "fgk"),
        (5, "MGK selbst", 3.0, "mgk_kaufteil_selbst"),
        (6, "MGK OEM", 5.0, "mgk_kaufteil_oem"),
    ]
    db.execute(text("DELETE FROM zuschlagssaetze"))
    for row_id, name, pct, typ in rates:
        if typ == missing_typ:
            continue
        db.execute(
            text(
                "INSERT INTO zuschlagssaetze (id, bezeichnung, satz_prozent, typ, aktiv) "
                "VALUES (:id, :name, :pct, :typ, 1)"
            ),
            {"id": row_id, "name": name, "pct": pct, "typ": typ},
        )
    db.commit()


def _post_recalculate(client: TestClient, baugruppe_id: int):
    return client.post(
        RECALCULATE_URL.format(baugruppe_id=baugruppe_id),
        json={"refresh_snapshots": False, "include_descendants": False},
    )


def _assert_missing_rate_422(response, expected_label: str) -> None:
    assert response.status_code == 422
    body = response.json()
    detail = body["detail"]
    assert isinstance(detail, str)
    assert "Fehlende aktive Zuschlagssätze" in detail
    assert expected_label in detail


def test_recalculate_http_missing_vvgk_422(client, db):
    top = _seed_structure_with_part_snapshot(db)
    _seed_markups_except(db, "vvgk")

    response = _post_recalculate(client, top.id)

    _assert_missing_rate_422(response, "vvgk")


def test_recalculate_http_missing_gewinn_422(client, db):
    top = _seed_structure_with_part_snapshot(db)
    _seed_markups_except(db, "gewinn")

    response = _post_recalculate(client, top.id)

    _assert_missing_rate_422(response, "gewinn")


def test_recalculate_http_missing_skonto_422(client, db):
    top = _seed_structure_with_part_snapshot(db)
    _seed_markups_except(db, "skonto")

    response = _post_recalculate(client, top.id)

    _assert_missing_rate_422(response, "skonto")


def test_recalculate_http_zero_percent_markups_200(client, db):
    top = _seed_structure_with_part_snapshot(db)
    _seed_markups(db, vvgk_pct=0, gewinn_pct=0, skonto_pct=0)

    response = _post_recalculate(client, top.id)

    assert response.status_code == 200
    body = response.json()
    assert body["calculation"]["markup_applied"] is True
    assert body["calculation"]["vvgk"] == pytest.approx(0.0)
    assert body["calculation"]["gewinn"] == pytest.approx(0.0)
    assert body["calculation"]["skonto"] == pytest.approx(0.0)
    assert not any(warning["code"] == "MISSING_MARKUP_RATE" for warning in body["warnings"])


def test_recalculate_http_top_level_markups_10_15_0_200(client, db):
    top = _seed_structure_with_part_snapshot(db)
    _seed_markups(db, vvgk_pct=10, gewinn_pct=15, skonto_pct=0)

    response = _post_recalculate(client, top.id)

    assert response.status_code == 200
    body = response.json()
    assert body["calculation"]["herstellkosten"] == pytest.approx(4.2)
    assert body["calculation"]["vvgk"] == pytest.approx(0.42)
    assert body["calculation"]["selbstkosten"] == pytest.approx(4.62)
    assert body["calculation"]["gewinn"] == pytest.approx(0.69)
    assert body["calculation"]["skonto"] == pytest.approx(0.0)
    assert body["calculation"]["endpreis_je_stueck"] == pytest.approx(5.31)
    assert body["calculation"]["markup_applied"] is True


def test_recalculate_http_inactive_vvgk_422(client, db):
    top = _seed_structure_with_part_snapshot(db)
    _seed_markups(db, vvgk_pct=10, gewinn_pct=15, skonto_pct=0)
    db.execute(text("UPDATE zuschlagssaetze SET aktiv = 0 WHERE typ = 'vvgk'"))
    db.commit()

    response = _post_recalculate(client, top.id)

    _assert_missing_rate_422(response, "vvgk")


def test_recalculate_http_duplicate_process_200(client, db):
    _seed_project(db)
    top = _top(db)
    db.execute(
        text(
            "INSERT INTO spritzguss_kalkulationen (id, teilebezeichnung, teilenummer, project_id, material_nominierung) "
            "VALUES (501, 'Träger', 'T-1', 100, 'selbstnominiert')"
        )
    )
    db.execute(
        text(
            "INSERT INTO veredelungsschritte (id, bezeichnung, veredelungsart, taktzeit_s) "
            "VALUES (33, 'Schäumen', 'Sonstige', 60)"
        )
    )
    db.execute(
        text(
            "INSERT INTO spritzguss_veredelung_zuordnungen "
            "(id, kalkulation_id, veredelungsschritt_id, reihenfolge, snapshot_bezeichnung, "
            "snapshot_kosten_inkl_ausschuss) "
            "VALUES (1, 501, 33, 1, 'Schäumen', 1.5)"
        )
    )
    _seed_markups(db, vvgk_pct=0, gewinn_pct=0, skonto_pct=0)
    _put(
        db,
        top.id,
        [
            _part_pos(sequence=1),
            AssemblyPositionInput(
                position_type="PROCESS",
                sequence=2,
                quantity=1,
                quantity_factor=1,
                finishing_step_id=33,
            ),
        ],
    )
    for pos in db.query(AssemblyPosition).filter(AssemblyPosition.parent_assembly_id == top.id).all():
        if pos.position_type == "PART":
            pos.cost_snapshot = 4.2
        elif pos.position_type == "PROCESS":
            pos.cost_snapshot = 1.5
        pos.snapshots_captured_at = datetime.now(UTC)
    db.commit()

    response = _post_recalculate(client, top.id)

    assert response.status_code == 200
    body = response.json()
    warning_codes = [warning["code"] for warning in body["warnings"]]
    assert "DUPLICATE_PROCESS_REVIEW" in warning_codes
    assert body["calculation"]["herstellkosten"] == pytest.approx(6.03)

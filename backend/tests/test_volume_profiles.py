"""Tests für Mengenprofil-Logik (SOP/EOP, Programm- und Projektvolumen)."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.customer import Customer
from app.models.program import Program, ProgramVolume
from app.models.project import Project
from app.schemas.hierarchy import ProgramVolumeBulkSave
from app.schemas.spritzguss_kalkulation import SpritzgussKalkulationCreate
from app.services.hierarchy import calendar_years_from_sop_eop, calculate_project_volume
from app.services.program_volume_service import (
    bulk_save_program_volumes,
    build_program_volume_profile,
    generate_years_from_sop_eop,
    years_with_data_outside_sop_eop,
)
from app.services.project_volume_service import (
    average_jahresstueckzahl_for_project,
    build_project_volume_profile,
)
from app.services.spritzguss_hierarchy import resolve_hierarchy_for_spritzguss


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    for table in (
        Customer.__table__,
        Program.__table__,
        ProgramVolume.__table__,
        Project.__table__,
    ):
        table.create(engine, checkfirst=True)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    session = Session()
    yield session
    session.close()


def _seed_hierarchy(db, *, qty: float = 2.0) -> tuple[Customer, Program, Project]:
    customer = Customer(customer_number="C-1", name="Testkunde")
    db.add(customer)
    db.flush()
    program = Program(
        customer_id=customer.id,
        program_number="P-1",
        name="Testprogramm",
        sop=date(2028, 1, 1),
        eop=date(2035, 12, 31),
    )
    db.add(program)
    db.flush()
    project = Project(
        program_id=program.id,
        project_number="PR-1",
        name="Testprojekt",
        component_area="Interior",
        quantity_per_vehicle=qty,
    )
    db.add(project)
    db.commit()
    return customer, program, project


def test_sop_eop_generates_eight_years():
    years = calendar_years_from_sop_eop(date(2028, 1, 1), date(2035, 12, 31))
    assert years == [2028, 2029, 2030, 2031, 2032, 2033, 2034, 2035]
    assert len(years) == 8


def test_generate_years_from_sop_eop_creates_rows(db):
    _, program, _ = _seed_hierarchy(db)
    years = generate_years_from_sop_eop(db, program.id)
    db.commit()
    assert len(years) == 8
    profile = build_program_volume_profile(db, program.id)
    assert len(profile["rows"]) == 8


def test_bulk_save_and_reload_volumes(db):
    _, program, _ = _seed_hierarchy(db)
    generate_years_from_sop_eop(db, program.id)
    items = [{"calendar_year": y, "vehicle_volume": 20_000 + (y - 2028) * 1000} for y in range(2028, 2036)]
    bulk_save_program_volumes(db, program.id, items)
    db.commit()
    profile = build_program_volume_profile(db, program.id)
    saved = {row["calendar_year"]: row["vehicle_volume"] for row in profile["rows"]}
    assert saved[2028] == 20_000
    assert saved[2035] == 27_000


def test_bulk_save_rejects_duplicate_years(db):
    from fastapi import HTTPException

    _, program, _ = _seed_hierarchy(db)
    with pytest.raises(HTTPException, match="Doppelte"):
        bulk_save_program_volumes(
            db,
            program.id,
            [
                {"calendar_year": 2028, "vehicle_volume": 1000},
                {"calendar_year": 2028, "vehicle_volume": 2000},
            ],
        )


def test_bulk_save_rejects_negative_vehicle_volume(db):
    _, program, _ = _seed_hierarchy(db)
    with pytest.raises(ValueError, match="negativ"):
        bulk_save_program_volumes(
            db,
            program.id,
            [{"calendar_year": 2028, "vehicle_volume": -1}],
        )


def test_sop_eop_shrink_warns_without_deleting(db):
    _, program, _ = _seed_hierarchy(db)
    bulk_save_program_volumes(
        db,
        program.id,
        [{"calendar_year": 2036, "vehicle_volume": 5000}],
    )
    db.commit()
    outside = years_with_data_outside_sop_eop(
        db,
        program.id,
        sop=date(2028, 1, 1),
        eop=date(2030, 12, 31),
    )
    assert 2036 in outside
    remaining = db.query(ProgramVolume).filter(ProgramVolume.program_id == program.id).all()
    assert any(v.calendar_year == 2036 for v in remaining)


def test_project_volume_quantity_2(db):
    _, program, project = _seed_hierarchy(db, qty=2.0)
    bulk_save_program_volumes(db, program.id, [{"calendar_year": 2028, "vehicle_volume": 20_000}])
    db.commit()
    profile = build_project_volume_profile(db, project.id)
    row = profile["rows"][0]
    assert row["project_volume"] == 40_000.0


def test_project_volume_quantity_1_5(db):
    _, program, project = _seed_hierarchy(db, qty=1.5)
    bulk_save_program_volumes(db, program.id, [{"calendar_year": 2028, "vehicle_volume": 20_000}])
    db.commit()
    profile = build_project_volume_profile(db, project.id)
    assert profile["rows"][0]["project_volume"] == 30_000.0


def test_calculate_project_volume_examples():
    assert calculate_project_volume(20_000, 2) == 40_000.0
    assert calculate_project_volume(20_000, 1.5) == 30_000.0


def test_spritzguss_create_without_calculation_year():
    calc = SpritzgussKalkulationCreate(
        teilebezeichnung="Teil",
        teilenummer="T-1",
        teilegewicht_netto_g=10,
        ausschussquote_pct=5,
        materialpreis_pro_kg=8,
        zykluszeit_s=30,
        kavitaeten=2,
        maschinenstundensatz=100,
        lohnstundensatz=50,
        werkzeugkosten_eur=0,
        werkzeug_abrechnungsart="einmalzahlung",
        customer_id=1,
        program_id=1,
        project_id=1,
    )
    assert calc.calculation_year is None


def test_spritzguss_create_still_requires_customer_program_project():
    with pytest.raises(ValidationError, match="Kunde, Programm und Projekt"):
        SpritzgussKalkulationCreate(
            teilebezeichnung="Teil",
            teilenummer="T-1",
            teilegewicht_netto_g=10,
            ausschussquote_pct=5,
            materialpreis_pro_kg=8,
            zykluszeit_s=30,
            kavitaeten=2,
            maschinenstundensatz=100,
            lohnstundensatz=50,
            werkzeugkosten_eur=0,
            werkzeug_abrechnungsart="einmalzahlung",
        )


def test_resolve_hierarchy_without_year_sets_names_only(db):
    customer, program, project = _seed_hierarchy(db)
    resolved = resolve_hierarchy_for_spritzguss(
        db,
        customer_id=customer.id,
        program_id=program.id,
        project_id=project.id,
    )
    assert resolved["kunde"] == "Testkunde"
    assert resolved["projekt"] == "Testprojekt"
    assert "jahresstueckzahl" not in resolved


def test_resolve_hierarchy_with_legacy_year(db):
    customer, program, project = _seed_hierarchy(db)
    bulk_save_program_volumes(db, program.id, [{"calendar_year": 2028, "vehicle_volume": 20_000}])
    db.commit()
    resolved = resolve_hierarchy_for_spritzguss(
        db,
        customer_id=customer.id,
        program_id=program.id,
        project_id=project.id,
        calculation_year=2028,
    )
    assert resolved["calculation_year"] == 2028
    assert resolved["jahresstueckzahl"] == 40_000


def test_average_jahresstueckzahl_ceil(db):
    """Durchschnitt = Summe / Jahre, aufgerundet mit ceil."""
    _, program, project = _seed_hierarchy(db, qty=1.0)
    # Jahre: 1000, 2000 → Ø 1500 → ceil 1500
    # Jahre: 1000, 1001 → Ø 1000.5 → ceil 1001
    bulk_save_program_volumes(
        db,
        program.id,
        [
            {"calendar_year": 2028, "vehicle_volume": 1000},
            {"calendar_year": 2029, "vehicle_volume": 1001},
        ],
    )
    db.commit()
    avg = average_jahresstueckzahl_for_project(db, project.id)
    assert avg.has_volumes is True
    assert avg.year_count == 2
    assert avg.sum_project_volume == 2001.0
    assert avg.jahresstueckzahl == 1001  # ceil(1000.5)


def test_average_jahresstueckzahl_with_quantity_per_vehicle(db):
    _, program, project = _seed_hierarchy(db, qty=2.5)
    bulk_save_program_volumes(
        db,
        program.id,
        [
            {"calendar_year": 2028, "vehicle_volume": 1000},  # 2500
            {"calendar_year": 2029, "vehicle_volume": 2000},  # 5000
        ],
    )
    db.commit()
    avg = average_jahresstueckzahl_for_project(db, project.id)
    # (2500+5000)/2 = 3750
    assert avg.jahresstueckzahl == 3750


def test_average_jahresstueckzahl_ohne_volumen(db):
    _, _, project = _seed_hierarchy(db)
    avg = average_jahresstueckzahl_for_project(db, project.id)
    assert avg.has_volumes is False
    assert avg.jahresstueckzahl is None
    assert avg.year_count == 0


def test_business_case_lifetime_revenue_calculation():
    endpreis = 3.5
    project_volume = 40_000.0
    assert round(project_volume * endpreis, 2) == 140_000.0

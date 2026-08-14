"""Tests für Hierarchie-Validierung, Programmstückzahlen und Spritzguss-Anbindung."""

import pytest
from pydantic import ValidationError

from app.schemas.hierarchy import ProjectCreate, ProjectUpdate
from app.services.hierarchy import (
    calculate_project_volume,
    validate_component_area,
    validate_quantity_per_vehicle,
)


def test_component_area_interior():
    assert validate_component_area("Interior") == "Interior"


def test_component_area_exterior():
    assert validate_component_area("Exterior") == "Exterior"


def test_component_area_other_rejected():
    with pytest.raises(ValueError, match="Interior"):
        validate_component_area("Türseitenverkleidung")


def test_project_create_interior():
    p = ProjectCreate(
        program_id=1,
        project_number="P-1",
        name="Test",
        component_area="Interior",
        quantity_per_vehicle=2,
    )
    assert p.component_area == "Interior"


def test_project_create_invalid_area():
    with pytest.raises(ValidationError):
        ProjectCreate(
            program_id=1,
            project_number="P-1",
            name="Test",
            component_area="ExteriorX",  # type: ignore[arg-type]
            quantity_per_vehicle=1,
        )


def test_quantity_per_vehicle_2():
    assert validate_quantity_per_vehicle(2) == 2


def test_quantity_per_vehicle_1_5():
    assert validate_quantity_per_vehicle(1.5) == 1.5


def test_quantity_per_vehicle_negative_rejected():
    with pytest.raises(ValueError):
        validate_quantity_per_vehicle(-1)


def test_project_volume_calculation():
    assert calculate_project_volume(20_000, 2) == 40_000.0


def test_project_update_validates_area():
    p = ProjectUpdate(component_area="Exterior")
    assert p.component_area == "Exterior"


def test_spritzguss_create_requires_hierarchy():
    from app.schemas.spritzguss_kalkulation import SpritzgussKalkulationCreate

    with pytest.raises(ValidationError, match="Kunde, Programm, Projekt"):
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

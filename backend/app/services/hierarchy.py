"""Validierung und Berechnung für Kunde → Programm → Projekt."""

from __future__ import annotations

MIN_CALENDAR_YEAR = 2000
MAX_CALENDAR_YEAR = 2100

COMPONENT_AREAS = ("Interior", "Exterior")


def validate_calendar_year(value: int) -> int:
    if value < MIN_CALENDAR_YEAR or value > MAX_CALENDAR_YEAR:
        raise ValueError(
            f"Kalenderjahr muss zwischen {MIN_CALENDAR_YEAR} und {MAX_CALENDAR_YEAR} liegen."
        )
    return value


def validate_vehicle_volume(value: int) -> int:
    if value < 0:
        raise ValueError("Fahrzeugstückzahl darf nicht negativ sein.")
    return value


def validate_quantity_per_vehicle(value: float) -> float:
    if value <= 0:
        raise ValueError("Anzahl pro Fahrzeug muss eine positive Zahl sein.")
    return value


def validate_component_area(value: str, *, strict: bool = True) -> str:
    """strict=True: nur Interior/Exterior; strict=False: historische Werte durchlassen."""
    if value in COMPONENT_AREAS:
        return value
    if strict:
        raise ValueError('Bauteilbereich muss "Interior" oder "Exterior" sein.')
    return value


def calculate_project_volume(vehicle_volume: int, quantity_per_vehicle: float) -> float:
    return round(vehicle_volume * quantity_per_vehicle, 2)

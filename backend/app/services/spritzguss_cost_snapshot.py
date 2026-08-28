"""Hilfsfunktionen für gespeicherte Spritzguss-Kostenwerte."""

from __future__ import annotations

from typing import Any


def selbstkosten_aus_ergebnis(ergebnis: dict[str, Any] | None) -> float | None:
    """Bevorzugt Selbstkosten/Herstellkosten gegenüber Verkaufspreis."""
    if not isinstance(ergebnis, dict):
        return None
    for key in ("selbstkosten", "herstellkosten", "gesamte_herstellkosten"):
        value = ergebnis.get(key)
        if value is not None:
            return float(value)
    return None


def verkaufspreis_aus_ergebnis(ergebnis: dict[str, Any] | None) -> float | None:
    if not isinstance(ergebnis, dict):
        return None
    preis = ergebnis.get("endpreis_je_stueck")
    if preis is None:
        preis = ergebnis.get("verkaufspreis")
    return float(preis) if preis is not None else None

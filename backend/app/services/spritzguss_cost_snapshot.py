"""Hilfsfunktionen für gespeicherte Spritzguss- und Baugruppen-Kostenwerte."""

from __future__ import annotations

from typing import Any


def _coerce_cost(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def _first_cost_from_dict(data: dict[str, Any] | None, keys: tuple[str, ...]) -> float | None:
    if not isinstance(data, dict):
        return None
    for key in keys:
        parsed = _coerce_cost(data.get(key))
        if parsed is not None:
            return parsed
    return None


def _cost_from_nested(
    ergebnis: dict[str, Any] | None,
    *,
    bloecke: dict[str, Any] | None = None,
) -> float | None:
    """Liest Selbstkosten/Herstellkosten aus Ergebnis und optionalen Blöcken."""
    cost_keys = (
        "selbstkosten",
        "herstellkosten",
        "gesamte_herstellkosten",
        "spritzguss_herstellkosten",
    )

    direct = _first_cost_from_dict(ergebnis, cost_keys)
    if direct is not None:
        return direct

    if isinstance(ergebnis, dict):
        gemeinkosten = ergebnis.get("gemeinkosten")
        nested = _first_cost_from_dict(gemeinkosten if isinstance(gemeinkosten, dict) else None, cost_keys)
        if nested is not None:
            return nested

    if isinstance(bloecke, dict):
        for block_key in ("zusammenfassung", "gemeinkosten"):
            block = bloecke.get(block_key)
            nested = _first_cost_from_dict(block if isinstance(block, dict) else None, cost_keys)
            if nested is not None:
                return nested

    return None


def selbstkosten_aus_ergebnis(
    ergebnis: dict[str, Any] | None,
    *,
    bloecke: dict[str, Any] | None = None,
) -> float | None:
    """Bevorzugt Selbstkosten/Herstellkosten – auch aus verschachtelten Blöcken."""
    return _cost_from_nested(ergebnis, bloecke=bloecke)


def herstellkosten_aus_baugruppe(
    ergebnis: dict[str, Any] | None,
    *,
    bloecke: dict[str, Any] | None = None,
) -> float | None:
    """Baugruppen-Herstellkosten/Selbstkosten aus Ergebnis und Blöcken."""
    cost_keys = ("herstellkosten", "selbstkosten", "gesamte_herstellkosten")
    direct = _first_cost_from_dict(ergebnis, cost_keys)
    if direct is not None:
        return direct

    if isinstance(bloecke, dict):
        for block_key in ("zusammenfassung", "gemeinkosten", "kosten"):
            block = bloecke.get(block_key)
            nested = _first_cost_from_dict(block if isinstance(block, dict) else None, cost_keys)
            if nested is not None:
                return nested

    return None


def verkaufspreis_aus_ergebnis(ergebnis: dict[str, Any] | None) -> float | None:
    if not isinstance(ergebnis, dict):
        return None
    preis = ergebnis.get("endpreis_je_stueck")
    if preis is None:
        preis = ergebnis.get("verkaufspreis")
    if preis is None:
        preis = ergebnis.get("baugruppenpreis_je_stueck")
    return float(preis) if preis is not None else None

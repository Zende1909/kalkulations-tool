"""Gemeinsames Parsing für DE/EN-Dezimalstrings in Pydantic-Schemas."""

from __future__ import annotations

from typing import Any


def parse_de_float(value: Any, *, field_label: str, allow_none: bool = True) -> float | None:
    """Akzeptiert float/int sowie Strings mit Komma oder Punkt (z. B. „44,1“)."""
    if value is None:
        if allow_none:
            return None
        raise ValueError(f"{field_label} ist Pflicht")
    if isinstance(value, bool):
        raise ValueError(f"{field_label} muss eine Zahl sein")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(" ", "").replace("\u00a0", "")
        if text == "":
            if allow_none:
                return None
            raise ValueError(f"{field_label} ist Pflicht")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError as exc:
            raise ValueError(
                f"{field_label} muss eine Zahl sein (z. B. 44,1 oder 44.1)"
            ) from exc
    raise ValueError(f"{field_label} muss eine Zahl sein")

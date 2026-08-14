"""Validierung und Berechnung für Investitionen."""

from __future__ import annotations

from fastapi import HTTPException, status

INVESTMENT_TYPES = (
    "Werkzeug",
    "Vorrichtung",
    "Maschine",
    "Prüfmittel",
    "Lehre",
    "Montageanlage",
    "Sonstige",
)

PAYMENT_TYPES = ("Amortisation", "Einmalzahlung")

STATUS_VALUES = (
    "In Planung",
    "Angefragt",
    "Bestellt",
    "In Herstellung",
    "Geliefert",
    "Abgenommen",
    "Abgeschlossen",
    "Storniert",
)

EINMALZAHLUNG_HINWEIS = "Separat, nicht im Stückpreis enthalten"


def _is_positive_int(value: float | int) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 1
    if isinstance(value, float):
        return value >= 1 and value == int(value)
    return False


def validate_amortization_volume(value: int | float | None) -> int | None:
    if value is None:
        return None
    if not _is_positive_int(value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Amortisationsvolumen muss eine positive ganze Zahl sein (z. B. 1 oder 20000).",
        )
    return int(value)


def compute_cost_per_piece(
    amount: float,
    payment_type: str,
    amortization_volume: int | None,
) -> float | None:
    if payment_type == "Einmalzahlung":
        return None
    if amortization_volume is None or amortization_volume < 1:
        return None
    return round(amount / amortization_volume, 6)


def resolve_included_in_unit_price(
    payment_type: str,
    calculation_id: int | None,
    explicit: bool | None = None,
) -> bool:
    if payment_type == "Einmalzahlung":
        return False
    if explicit is not None:
        return explicit
    return calculation_id is not None


def validate_investition_input(
    *,
    name: str,
    investment_type: str,
    payment_type: str,
    amount: float,
    amortization_volume: int | float | None,
    status_value: str,
    calculation_id: int | None = None,
    included_in_unit_price: bool | None = None,
) -> dict:
    if not name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Investitionsbezeichnung ist erforderlich.",
        )
    if investment_type not in INVESTMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ungültige Investitionsart: {investment_type}",
        )
    if payment_type not in PAYMENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ungültige Zahlungsart: {payment_type}",
        )
    if amount < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Investitionsbetrag darf nicht negativ sein.",
        )
    if status_value not in STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ungültiger Status: {status_value}",
        )

    volume: int | None
    if payment_type == "Einmalzahlung":
        volume = None
    else:
        if amortization_volume is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Bei Amortisation ist das Amortisationsvolumen erforderlich.",
            )
        volume = validate_amortization_volume(amortization_volume)

    cost = compute_cost_per_piece(amount, payment_type, volume)
    included = resolve_included_in_unit_price(payment_type, calculation_id, included_in_unit_price)

    return {
        "amortization_volume": volume,
        "cost_per_piece": cost,
        "included_in_unit_price": included,
    }


def investition_display_name(row) -> str:
    if getattr(row, "name", None):
        return row.name
    if row.description:
        return row.description
    return row.part_name or f"Investition #{row.id}"


def zuordnung_label(
    *,
    calculation_id: int | None,
    baugruppe_id: int | None,
    part_number: str,
    part_name: str,
    project_id: str,
    calc_teilenummer: str | None = None,
    calc_bezeichnung: str | None = None,
    bg_name: str | None = None,
    bg_teilenummer: str | None = None,
) -> str:
    if calculation_id is not None:
        nummer = calc_teilenummer or part_number
        bez = calc_bezeichnung or part_name
        if nummer and bez:
            return f"Einzelteil: {nummer} – {bez}"
        return f"Einzelteil #{calculation_id}"
    if baugruppe_id is not None:
        nummer = bg_teilenummer or part_number
        name = bg_name or part_name
        if nummer and name:
            return f"Baugruppe: {nummer} – {name}"
        return f"Baugruppe #{baugruppe_id}"
    if part_number:
        return part_number
    if project_id:
        return f"Projekt: {project_id}"
    return "–"

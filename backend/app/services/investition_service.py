"""Validierung und Berechnung für projektbezogene Investitionsplanung."""

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

# Optionaler Planungsstatus – kein Beschaffungs-/Lieferstatus
PLANNING_STATUS_VALUES = ("Geplant", "Berücksichtigt", "Entfällt")

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
    baugruppe_id: int | None = None,
    explicit: bool | None = None,
) -> bool:
    """Investitionen fließen nicht automatisch in den Teilepreis ein."""
    return False


def validate_non_negative_amount(value: float | None, label: str) -> float | None:
    if value is None:
        return None
    if value < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{label} darf nicht negativ sein.",
        )
    return float(value)


def validate_investition_input(
    *,
    name: str,
    investment_type: str,
    payment_type: str,
    cost_amount: float,
    bottom_price: float | None = None,
    revenue_amount: float | None = None,
    amortization_volume: int | float | None,
    project: str,
    calculation_id: int | None = None,
    baugruppe_id: int | None = None,
    included_in_unit_price: bool | None = None,
    planning_status: str | None = None,
) -> dict:
    if not name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Investitionsbezeichnung ist erforderlich.",
        )
    if not project.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Projekt ist für den Business Case erforderlich.",
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
    cost = validate_non_negative_amount(cost_amount, "Kosten") or 0.0
    bottom = validate_non_negative_amount(bottom_price, "Bottom Price")
    revenue = validate_non_negative_amount(revenue_amount, "Erlös")
    if planning_status and planning_status not in PLANNING_STATUS_VALUES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Ungültiger Planungsstatus: {planning_status}",
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

    cost_piece = compute_cost_per_piece(cost, payment_type, volume)
    included = resolve_included_in_unit_price(
        payment_type, calculation_id, baugruppe_id, included_in_unit_price
    )

    return {
        "cost_amount": cost,
        "amount": cost,
        "bottom_price": bottom,
        "revenue_amount": revenue,
        "amortization_volume": volume,
        "cost_per_piece": cost_piece,
        "included_in_unit_price": included,
        "status": planning_status or "",
    }


def zuordnung_label(
    *,
    calculation_id: int | None,
    baugruppe_id: int | None,
    kaufteil_id: int | None = None,
    assignment_type: str | None = None,
    part_number: str,
    part_name: str,
    project_id: str,
    calc_teilenummer: str | None = None,
    calc_bezeichnung: str | None = None,
    bg_name: str | None = None,
    bg_teilenummer: str | None = None,
    kt_bezeichnung: str | None = None,
    kt_artikelnummer: str | None = None,
    customer_name: str | None = None,
    program_name: str | None = None,
    project_name: str | None = None,
) -> str:
    from app.services.investition_assignment_service import (
        ASSIGNMENT_TYPE_LABELS,
        infer_assignment_type,
    )

    atype = infer_assignment_type(
        assignment_type=assignment_type,
        calculation_id=calculation_id,
        baugruppe_id=baugruppe_id,
        kaufteil_id=kaufteil_id,
    )
    if atype == "einzelteil" or calculation_id is not None:
        nummer = calc_teilenummer or part_number
        bez = calc_bezeichnung or part_name
        if nummer and bez:
            return f"Einzelteil: {nummer} – {bez}"
        return f"Einzelteil #{calculation_id}"
    if atype == "kaufteil" or kaufteil_id is not None:
        nummer = kt_artikelnummer or part_number
        bez = kt_bezeichnung or part_name
        if nummer and bez:
            return f"Kaufteil: {nummer} – {bez}"
        return f"Kaufteil #{kaufteil_id}"
    if atype == "baugruppe" or baugruppe_id is not None:
        nummer = bg_teilenummer or part_number
        name = bg_name or part_name
        if nummer and name:
            return f"Baugruppe: {nummer} – {name}"
        return f"Baugruppe #{baugruppe_id}"
    label_project = project_name or project_id
    if customer_name and program_name and label_project:
        return f"Gesamtprojekt: {customer_name} / {program_name} / {label_project}"
    if label_project:
        return f"Gesamtprojekt: {label_project}"
    return "Gesamtprojekt"

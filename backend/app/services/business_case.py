"""Business-Case-Aggregation: Kalkulationspreise + Investitionsplanung."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.dashboard import (
    endpreis_aus_spritzguss,
    jahresumsatz_aus_baugruppe,
    preis_aus_baugruppe,
)
from app.services.investition_financials import (
    aggregate_investment_financials,
    build_investment_financial_view,
    effective_cost_amount,
)
from app.services.investition_service import EINMALZAHLUNG_HINWEIS, compute_cost_per_piece


@dataclass(frozen=True)
class InvestitionSnapshot:
    id: int
    name: str
    investment_type: str
    payment_type: str
    amount: float
    amortization_volume: int | None
    cost_per_piece: float | None
    project_id: str
    customer: str
    calculation_id: int | None
    baugruppe_id: int | None
    included_in_unit_price: bool
    archived: bool
    kaufteil_id: int | None = None
    assignment_type: str | None = None
    linked_project_id: int | None = None
    part_number: str = ""
    cost_amount: float | None = None
    bottom_price: float | None = None
    revenue_amount: float | None = None


@dataclass(frozen=True)
class CalcSnapshot:
    id: int
    teilenummer: str
    teilebezeichnung: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    ergebnis: dict | None


@dataclass(frozen=True)
class BaugruppeSnapshot:
    id: int
    name: str
    teilenummer: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    ergebnis: dict | None


def filter_investitionen(
    rows: list[InvestitionSnapshot],
    *,
    project: str | None = None,
    customer: str | None = None,
    linked_project_id: int | None = None,
    calculation_id: int | None = None,
    baugruppe_id: int | None = None,
    kaufteil_id: int | None = None,
    scope: str | None = None,
) -> list[InvestitionSnapshot]:
    result = [r for r in rows if not r.archived]
    if linked_project_id is not None:
        result = [r for r in result if r.linked_project_id == linked_project_id]
    elif project:
        result = [r for r in result if r.project_id == project]
    if customer:
        result = [r for r in result if r.customer == customer]
    if calculation_id is not None:
        result = [r for r in result if r.calculation_id == calculation_id]
    elif baugruppe_id is not None:
        result = [r for r in result if r.baugruppe_id == baugruppe_id]
    elif kaufteil_id is not None:
        result = [r for r in result if r.kaufteil_id == kaufteil_id]
    elif scope == "gesamtprojekt":
        result = [
            r
            for r in result
            if r.calculation_id is None and r.baugruppe_id is None and r.kaufteil_id is None
        ]
    elif scope == "einzelteil":
        result = [r for r in result if r.calculation_id is not None]
    elif scope == "baugruppe":
        result = [r for r in result if r.baugruppe_id is not None]
    elif scope == "kaufteil":
        result = [r for r in result if r.kaufteil_id is not None]
    return result


def _investition_applies_to_scope(
    inv: InvestitionSnapshot,
    *,
    calculation_id: int | None,
    baugruppe_id: int | None,
    kaufteil_id: int | None = None,
) -> bool:
    if calculation_id is not None:
        return inv.calculation_id == calculation_id
    if baugruppe_id is not None:
        return inv.baugruppe_id == baugruppe_id
    if kaufteil_id is not None:
        return inv.kaufteil_id == kaufteil_id
    return inv.calculation_id is None and inv.baugruppe_id is None and inv.kaufteil_id is None


def _inv_cost(inv: InvestitionSnapshot) -> float:
    return effective_cost_amount(cost_amount=inv.cost_amount, amount=inv.amount)


def _scoped_financial_rows(scoped: list[InvestitionSnapshot]) -> list[dict]:
    rows: list[dict] = []
    for inv in scoped:
        financials = build_investment_financial_view(
            cost_amount=inv.cost_amount,
            bottom_price=inv.bottom_price,
            revenue_amount=inv.revenue_amount,
            legacy_amount=inv.amount,
        )
        rows.append(
            {
                **financials,
                "id": inv.id,
                "assignment_type": inv.assignment_type,
                "calculation_id": inv.calculation_id,
                "baugruppe_id": inv.baugruppe_id,
                "kaufteil_id": inv.kaufteil_id,
            }
        )
    return rows


def build_business_case(
    investitionen: list[InvestitionSnapshot],
    *,
    project: str | None = None,
    customer: str | None = None,
    calculation_id: int | None = None,
    baugruppe_id: int | None = None,
    calc: CalcSnapshot | None = None,
    baugruppe: BaugruppeSnapshot | None = None,
    scope: str | None = None,
) -> dict:
    scoped = filter_investitionen(
        investitionen,
        project=project,
        customer=customer,
        calculation_id=calculation_id,
        baugruppe_id=baugruppe_id,
        scope=scope,
    )

    teilepreis = endpreis_aus_spritzguss(calc.ergebnis) if calc else None
    baugruppenpreis = preis_aus_baugruppe(baugruppe.ergebnis) if baugruppe else None

    jahresstueckzahl: int | None = None
    if calc is not None:
        jahresstueckzahl = calc.jahresstueckzahl
    elif baugruppe is not None:
        jahresstueckzahl = baugruppe.jahresstueckzahl

    jahresumsatz: float | None = None
    if baugruppe is not None:
        jahresumsatz = jahresumsatz_aus_baugruppe(baugruppe.ergebnis, baugruppe.jahresstueckzahl)
    elif calc is not None and teilepreis is not None and calc.jahresstueckzahl > 0:
        jahresumsatz = round(teilepreis * calc.jahresstueckzahl, 2)

    investitionen_gesamt = round(sum(_inv_cost(r) for r in scoped), 2)
    amort_gesamt = round(
        sum(_inv_cost(r) for r in scoped if r.payment_type == "Amortisation"),
        2,
    )
    einmal_gesamt = round(
        sum(_inv_cost(r) for r in scoped if r.payment_type == "Einmalzahlung"),
        2,
    )
    financial_rows = _scoped_financial_rows(scoped)
    financial_summary = aggregate_investment_financials(financial_rows)

    amort_anteil = 0.0
    if calculation_id is not None or baugruppe_id is not None:
        for inv in scoped:
            if inv.payment_type != "Amortisation":
                continue
            if not _investition_applies_to_scope(
                inv, calculation_id=calculation_id, baugruppe_id=baugruppe_id
            ):
                continue
            piece = inv.cost_per_piece
            if piece is None and inv.amortization_volume:
                piece = compute_cost_per_piece(
                    _inv_cost(inv), inv.payment_type, inv.amortization_volume
                )
            if piece is not None:
                amort_anteil += piece
    amort_anteil = round(amort_anteil, 2)

    basis_preis = baugruppenpreis if baugruppe_id is not None else teilepreis
    # Investitionen werden separat ausgewiesen und nicht zum Teile-/Baugruppenpreis addiert.
    preis_inkl_amort = round(basis_preis, 2) if basis_preis is not None else None

    einmal_positionen = [
        {
            "id": r.id,
            "name": r.name,
            "amount": _inv_cost(r),
            "cost_amount": _inv_cost(r),
            "bottom_price": r.bottom_price,
            "revenue_amount": r.revenue_amount,
            "hinweis": EINMALZAHLUNG_HINWEIS,
        }
        for r in scoped
        if r.payment_type == "Einmalzahlung"
    ]

    totals = financial_summary["totals"]
    return {
        "filter": {
            "project": project,
            "customer": customer,
            "calculation_id": calculation_id,
            "baugruppe_id": baugruppe_id,
        },
        "teilepreis_je_stueck": teilepreis,
        "baugruppenpreis_je_stueck": baugruppenpreis,
        "jahresstueckzahl": jahresstueckzahl,
        "jahresumsatz": jahresumsatz,
        "investitionen_gesamt": investitionen_gesamt,
        "amortisationsinvestitionen_gesamt": amort_gesamt,
        "einmalinvestitionen_gesamt": einmal_gesamt,
        "investition_cost_total": totals["cost_amount_total"],
        "investition_bottom_price_total": totals["bottom_price_total"],
        "investition_revenue_total": totals["revenue_amount_total"],
        "margin_revenue_minus_cost_total": totals["margin_revenue_minus_cost_total"],
        "margin_revenue_minus_bottom_price_total": totals["margin_revenue_minus_bottom_price_total"],
        "margin_bottom_price_minus_cost_total": totals["margin_bottom_price_minus_cost_total"],
        "investition_financial_summary": financial_summary,
        "amortisationsanteil_je_stueck": amort_anteil if (calculation_id or baugruppe_id) else None,
        "preis_inkl_amortisation_je_stueck": preis_inkl_amort,
        "einmalinvestitionen": einmal_positionen,
        "anzahl_investitionen": len(scoped),
        "hat_gespeicherte_kalkulation": calc is not None or baugruppe is not None,
    }

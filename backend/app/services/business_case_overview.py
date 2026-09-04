"""Projektbezogene Business-Case-Gesamtübersicht."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.baugruppe import (
    Baugruppe,
    BaugruppeKaufteilZuordnung,
    BaugruppeSpritzgussZuordnung,
    BaugruppeVeredelungZuordnung,
)
from app.models.customer import Customer
from app.models.investition import Investition
from app.models.program import Program
from app.models.project import Project
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.services.business_case_kpis import build_business_case_kpis
from app.services.business_case_pricing import (
    aggregate_sales_totals,
    build_position_pricing,
    build_revenue_by_year,
    kosten_aus_baugruppe,
    kosten_aus_spritzguss,
    load_manual_prices_map,
    revenue_margin_percent,
)
from app.services.dashboard import endpreis_aus_spritzguss, jahresumsatz_aus_baugruppe, parse_json_dict, preis_aus_baugruppe
from app.services.investition_assignment_service import ASSIGNMENT_TYPE_LABELS, infer_assignment_type
from app.services.investition_financials import (
    aggregate_investment_financials,
    build_investment_financial_view,
    effective_cost_amount,
)
from app.services.investition_service import (
    is_capex,
    is_entwicklung,
    payment_hint_for,
    zuordnung_label,
)
from app.services.project_volume_service import build_project_volume_profile


def _load_hierarchy_context(
    db: Session,
    *,
    customer_id: int,
    program_id: int,
    linked_project_id: int,
) -> tuple[Customer, Program, Project]:
    customer = db.get(Customer, customer_id)
    program = db.get(Program, program_id)
    project = db.get(Project, linked_project_id)
    if customer is None or program is None or project is None:
        raise ValueError("Kunde, Programm oder Projekt nicht gefunden.")
    if program.customer_id != customer.id:
        raise ValueError("Programm passt nicht zum Kunden.")
    if project.program_id != program.id:
        raise ValueError("Projekt passt nicht zum Programm.")
    return customer, program, project


def _spritzguss_in_project(db: Session, linked_project_id: int) -> list[SpritzgussKalkulation]:
    return list(
        db.scalars(
            select(SpritzgussKalkulation).where(
                SpritzgussKalkulation.project_id == linked_project_id,
            )
        ).all()
    )


def _baugruppen_in_project(db: Session, linked_project_id: int) -> list[Baugruppe]:
    return list(
        db.scalars(
            select(Baugruppe).where(
                or_(
                    Baugruppe.linked_project_id == linked_project_id,
                    Baugruppe.project_id == linked_project_id,
                )
            )
        ).all()
    )


def _spritzguss_ids_in_baugruppen(db: Session, baugruppe_ids: list[int]) -> set[int]:
    if not baugruppe_ids:
        return set()
    rows = db.scalars(
        select(BaugruppeSpritzgussZuordnung.spritzguss_kalkulation_id).where(
            BaugruppeSpritzgussZuordnung.baugruppe_id.in_(baugruppe_ids)
        )
    ).all()
    return {int(r) for r in rows}


def _project_volume(db: Session, project_id: int) -> float:
    try:
        profile = build_project_volume_profile(db, project_id)
        return float(profile["total_project_volume"])
    except Exception:
        return 0.0


def build_project_business_case(
    db: Session,
    *,
    customer_id: int,
    program_id: int,
    linked_project_id: int,
    calculation_id: int | None = None,
    baugruppe_id: int | None = None,
) -> dict:
    customer, program, project = _load_hierarchy_context(
        db,
        customer_id=customer_id,
        program_id=program_id,
        linked_project_id=linked_project_id,
    )
    customer_name = customer.name
    program_name = program.name
    project_name = project.name

    sg_rows = _spritzguss_in_project(db, linked_project_id)
    if calculation_id is not None:
        sg_rows = [r for r in sg_rows if r.id == calculation_id]

    bg_rows = _baugruppen_in_project(db, linked_project_id)
    if baugruppe_id is not None:
        bg_rows = [r for r in bg_rows if r.id == baugruppe_id]

    linked_sg_ids = _spritzguss_ids_in_baugruppen(db, [bg.id for bg in bg_rows])
    standalone_sg_rows = [r for r in sg_rows if r.id not in linked_sg_ids]

    manual_map = load_manual_prices_map(
        db,
        customer_id=customer_id,
        program_id=program_id,
        linked_project_id=linked_project_id,
    )
    project_volume_default = _project_volume(db, linked_project_id)

    sg_map = {r.id: r for r in sg_rows}
    bg_map = {r.id: r for r in bg_rows}

    parts: list[dict] = []
    sales_positions: list[dict] = []
    for row in standalone_sg_rows:
        ergebnis = parse_json_dict(row.ergebnis)
        bloecke = parse_json_dict(row.ergebnis_bloecke)
        cost = kosten_aus_spritzguss(ergebnis, bloecke=bloecke)
        endpreis = endpreis_aus_spritzguss(ergebnis)
        manual = manual_map.get(("einzelteil", row.id))
        bottom = manual.bottom_price_per_piece if manual else None
        actual = manual.actual_price_per_piece if manual else None
        volume = project_volume_default or float(row.jahresstueckzahl or 0)
        pricing = build_position_pricing(
            cost_per_piece=cost,
            bottom_price_per_piece=bottom,
            actual_price_per_piece=actual,
            project_volume=volume,
        )
        vd_count = db.scalar(
            select(func.count())
            .select_from(SpritzgussVeredelungZuordnung)
            .where(SpritzgussVeredelungZuordnung.kalkulation_id == row.id)
        ) or 0
        part_row = {
            "id": row.id,
            "assignment_type": "einzelteil",
            "bezeichnung": row.teilebezeichnung,
            "teilenummer": row.teilenummer,
            "material_number": row.teilenummer,
            "kunde": customer_name,
            "program": program_name,
            "projekt": project_name,
            "customer_id": customer_id,
            "program_id": program_id,
            "linked_project_id": linked_project_id,
            "jahresstueckzahl": row.jahresstueckzahl,
            "gesamtstueckzahl_laufzeit": volume,
            "endpreis_je_stueck": endpreis,
            "anzahl_veredelungsschritte": int(vd_count),
            **pricing,
        }
        parts.append(part_row)
        sales_positions.append(pricing | {"project_volume": volume})

    assemblies: list[dict] = []
    for row in bg_rows:
        ergebnis = parse_json_dict(row.ergebnis)
        bloecke = parse_json_dict(row.ergebnis_bloecke)
        cost = kosten_aus_baugruppe(ergebnis, bloecke=bloecke)
        baugruppenpreis = preis_aus_baugruppe(ergebnis)
        manual = manual_map.get(("baugruppe", row.id))
        bottom = manual.bottom_price_per_piece if manual else None
        actual = manual.actual_price_per_piece if manual else None
        volume = project_volume_default or float(row.jahresstueckzahl or 0)
        pricing = build_position_pricing(
            cost_per_piece=cost,
            bottom_price_per_piece=bottom,
            actual_price_per_piece=actual,
            project_volume=volume,
        )
        jahresumsatz = jahresumsatz_aus_baugruppe(ergebnis, row.jahresstueckzahl)
        sg_count = db.scalar(
            select(func.count())
            .select_from(BaugruppeSpritzgussZuordnung)
            .where(BaugruppeSpritzgussZuordnung.baugruppe_id == row.id)
        ) or 0
        kt_count = db.scalar(
            select(func.count())
            .select_from(BaugruppeKaufteilZuordnung)
            .where(BaugruppeKaufteilZuordnung.baugruppe_id == row.id)
        ) or 0
        vd_count = db.scalar(
            select(func.count())
            .select_from(BaugruppeVeredelungZuordnung)
            .where(BaugruppeVeredelungZuordnung.baugruppe_id == row.id)
        ) or 0
        assembly_row = {
            "id": row.id,
            "assignment_type": "baugruppe",
            "name": row.name,
            "teilenummer": row.teilenummer,
            "material_number": row.teilenummer,
            "kunde": customer_name,
            "program": program_name,
            "projekt": project_name,
            "customer_id": customer_id,
            "program_id": program_id,
            "linked_project_id": linked_project_id,
            "jahresstueckzahl": row.jahresstueckzahl,
            "gesamtstueckzahl_laufzeit": volume,
            "baugruppenpreis_je_stueck": baugruppenpreis,
            "jahresumsatz": jahresumsatz,
            "umsatzpotenzial_laufzeit": pricing["actual_revenue"] or jahresumsatz,
            "anzahl_einzelteile": int(sg_count),
            "anzahl_kaufteile": int(kt_count),
            "anzahl_veredelungsschritte": int(vd_count),
            **pricing,
        }
        assemblies.append(assembly_row)
        sales_positions.append(pricing | {"project_volume": volume})

    inv_rows = list(
        db.scalars(
            select(Investition).where(
                Investition.archived.is_(False),
                Investition.linked_project_id == linked_project_id,
                Investition.customer_id == customer_id,
                Investition.program_id == program_id,
            )
        ).all()
    )

    investments: list[dict] = []
    investments_capex: list[dict] = []
    investments_entwicklung: list[dict] = []
    investments_other: list[dict] = []
    financial_rows: list[dict] = []
    amort_gesamt = 0.0
    einmal_gesamt = 0.0
    capex_gesamt = 0.0
    entwicklung_gesamt = 0.0
    amort_anteil_summe = 0.0
    for inv in inv_rows:
        calc = sg_map.get(inv.calculation_id) if inv.calculation_id else None
        bg = bg_map.get(inv.baugruppe_id) if inv.baugruppe_id else None
        piece = float(inv.cost_per_piece) if inv.cost_per_piece is not None else None
        cost = effective_cost_amount(
            cost_amount=getattr(inv, "cost_amount", None),
            amount=inv.amount,
        )
        financials = build_investment_financial_view(
            cost_amount=getattr(inv, "cost_amount", cost),
            bottom_price=getattr(inv, "bottom_price", None),
            revenue_amount=getattr(inv, "revenue_amount", None),
            legacy_amount=inv.amount,
            payment_type=inv.payment_type,
        )
        if is_capex(inv.payment_type):
            financials["margin_revenue_minus_cost_pct"] = None
            financials["margin_revenue_minus_bottom_price_pct"] = None
        else:
            financials["margin_revenue_minus_cost_pct"] = revenue_margin_percent(
                financials["revenue_amount"], financials["cost_amount"]
            )
            financials["margin_revenue_minus_bottom_price_pct"] = revenue_margin_percent(
                financials["revenue_amount"], financials["bottom_price"]
            )
        atype = infer_assignment_type(
            assignment_type=getattr(inv, "assignment_type", None),
            calculation_id=inv.calculation_id,
            baugruppe_id=inv.baugruppe_id,
            kaufteil_id=getattr(inv, "kaufteil_id", None),
        )
        if inv.payment_type == "Amortisation":
            amort_gesamt += cost
            if piece is not None:
                amort_anteil_summe += piece
        elif is_capex(inv.payment_type):
            capex_gesamt += cost
        elif is_entwicklung(inv.payment_type):
            entwicklung_gesamt += cost
        elif inv.payment_type == "Einmalzahlung":
            einmal_gesamt += cost
        hint = payment_hint_for(inv.payment_type)
        material_number = inv.part_number or ""
        if atype == "einzelteil" and calc is not None:
            material_number = calc.teilenummer or material_number
        elif atype == "baugruppe" and bg is not None:
            material_number = bg.teilenummer or material_number
        elif atype == "gesamtprojekt":
            material_number = ""
        row = {
            "id": inv.id,
            "bezeichnung": inv.name or inv.description or inv.part_name,
            "investment_type": inv.investment_type,
            "payment_type": inv.payment_type,
            "amount": cost,
            "cost_amount": financials["cost_amount"],
            "bottom_price": financials["bottom_price"],
            "revenue_amount": financials["revenue_amount"],
            "margin_revenue_minus_cost": financials["margin_revenue_minus_cost"],
            "margin_revenue_minus_bottom_price": financials["margin_revenue_minus_bottom_price"],
            "margin_bottom_price_minus_cost": financials["margin_bottom_price_minus_cost"],
            "margin_revenue_minus_cost_pct": financials["margin_revenue_minus_cost_pct"],
            "margin_revenue_minus_bottom_price_pct": financials["margin_revenue_minus_bottom_price_pct"],
            "amount_warnings": financials["warnings"],
            "assignment_type": atype,
            "assignment_type_label": ASSIGNMENT_TYPE_LABELS.get(atype or "", ""),
            "material_number": material_number,
            "part_number": material_number,
            "customer_name": customer_name,
            "program_name": program_name,
            "project_name": project_name,
            "customer_id": inv.customer_id,
            "program_id": inv.program_id,
            "linked_project_id": inv.linked_project_id,
            "amortization_volume": inv.amortization_volume,
            "cost_per_piece": piece,
            "zuordnung": zuordnung_label(
                calculation_id=inv.calculation_id,
                baugruppe_id=inv.baugruppe_id,
                kaufteil_id=getattr(inv, "kaufteil_id", None),
                assignment_type=atype,
                part_number=inv.part_number or "",
                part_name=inv.part_name or "",
                project_id=project_name,
                calc_teilenummer=calc.teilenummer if calc else None,
                calc_bezeichnung=calc.teilebezeichnung if calc else None,
                bg_name=bg.name if bg else None,
                bg_teilenummer=bg.teilenummer if bg else None,
                customer_name=customer_name,
                program_name=program_name,
                project_name=project_name,
            ),
            "hinweis": hint,
            "bemerkung": inv.description or "",
        }
        investments.append(row)
        if is_capex(inv.payment_type):
            investments_capex.append(row)
        elif is_entwicklung(inv.payment_type):
            investments_entwicklung.append(row)
        else:
            investments_other.append(row)
        financial_rows.append(
            {
                **financials,
                "payment_type": inv.payment_type,
                "assignment_type": atype,
                "calculation_id": inv.calculation_id,
                "baugruppe_id": inv.baugruppe_id,
                "kaufteil_id": getattr(inv, "kaufteil_id", None),
            }
        )

    sales_totals = aggregate_sales_totals(sales_positions)
    investment_financial_summary = aggregate_investment_financials(financial_rows)
    fin_totals = investment_financial_summary["totals"]
    fin_capex = investment_financial_summary["capex"]
    fin_entwicklung = investment_financial_summary["entwicklung"]
    fin_legacy = investment_financial_summary["legacy"]
    investitionen_gesamt = round(fin_totals["cost_amount_total"], 2)
    kpi_summary = build_business_case_kpis(
        sales_totals=sales_totals,
        investment_financial_summary=investment_financial_summary,
        parts=parts,
        assemblies=assemblies,
    )
    total_kpis = kpi_summary["total"]
    operating = kpi_summary["operating"]
    capital = kpi_summary["capital"]

    excluded_in_baugruppe_count = len(linked_sg_ids & {r.id for r in sg_rows})

    try:
        volume_profile = build_project_volume_profile(db, linked_project_id)
        volume_rows = list(volume_profile.get("rows") or [])
    except Exception:
        volume_rows = []
    revenue_by_year = build_revenue_by_year(parts + assemblies, volume_rows)

    return {
        "filter": {
            "customer_id": customer_id,
            "program_id": program_id,
            "linked_project_id": linked_project_id,
            "customer": customer_name,
            "program": program_name,
            "project": project_name,
        },
        "project": project_name,
        "customer": customer_name,
        "program": program_name,
        "customer_id": customer_id,
        "program_id": program_id,
        "linked_project_id": linked_project_id,
        "kpis": {
            "kunde": customer_name,
            "programm": program_name,
            "projekt": project_name,
            "customer_id": customer_id,
            "program_id": program_id,
            "linked_project_id": linked_project_id,
            "project_volume_total": sales_totals["project_volume_total"],
            "parts_cost_total": sales_totals["cost_total"],
            "operative_cost_total": operating["cost_total"],
            "cost_total": operating["cost_total"],
            "bound_capital_total": capital["bound_capital_total"],
            "capex_cost_total": capital["capex_total"],
            "non_capex_investment_cost_total": capital["non_capex_investment_cost_total"],
            "bottom_price_revenue_total": total_kpis["bottom_price_revenue_total"],
            "actual_revenue_total": total_kpis["actual_revenue_total"],
            "parts_bottom_price_revenue_total": sales_totals["bottom_price_revenue_total"],
            "parts_actual_revenue_total": sales_totals["actual_revenue_total"],
            "margin_bottom_price_total": sales_totals["margin_bottom_price_total"],
            "margin_actual_total": sales_totals["margin_actual_total"],
            "margin_bottom_price_total_pct": sales_totals["margin_bottom_price_total_pct"],
            "margin_actual_total_pct": sales_totals["margin_actual_total_pct"],
            "ebit_bottom_total": operating["ebit_bottom"],
            "ebit_bottom_total_pct": operating["ebit_bottom_pct"],
            "ebit_actual_total": operating["ebit_actual"],
            "ebit_actual_total_pct": operating["ebit_actual_pct"],
            "roi_bottom_pct": capital["roi_incl_capex_bottom_pct"],
            "roi_actual_pct": capital["roi_incl_capex_actual_pct"],
            "roi_incl_capex_bottom_pct": capital["roi_incl_capex_bottom_pct"],
            "roi_incl_capex_actual_pct": capital["roi_incl_capex_actual_pct"],
            "roi_operating_bottom_pct": operating["roi_operating_bottom_pct"],
            "roi_operating_actual_pct": operating["roi_operating_actual_pct"],
            "parts_ebit_bottom": kpi_summary["parts"]["ebit_bottom"],
            "parts_ebit_bottom_pct": kpi_summary["parts"]["ebit_bottom_pct"],
            "parts_ebit_actual": kpi_summary["parts"]["ebit_actual"],
            "parts_ebit_actual_pct": kpi_summary["parts"]["ebit_actual_pct"],
            "parts_roi_bottom_pct": kpi_summary["parts"]["roi_bottom_pct"],
            "parts_roi_actual_pct": kpi_summary["parts"]["roi_actual_pct"],
            "investments_ebit_bottom": kpi_summary["investments_operating"]["ebit_bottom"],
            "investments_ebit_bottom_pct": kpi_summary["investments_operating"]["ebit_bottom_pct"],
            "investments_ebit_actual": kpi_summary["investments_operating"]["ebit_actual"],
            "investments_ebit_actual_pct": kpi_summary["investments_operating"]["ebit_actual_pct"],
            "investments_roi_bottom_pct": kpi_summary["investments_operating"]["roi_bottom_pct"],
            "investments_roi_actual_pct": kpi_summary["investments_operating"]["roi_actual_pct"],
            "anzahl_einzelteile": len(parts),
            "anzahl_baugruppen": len(assemblies),
            "anzahl_einzelteile_in_baugruppen_ausgeschlossen": excluded_in_baugruppe_count,
            "anzahl_investitionen": len(investments),
            "investitionen_gesamt": investitionen_gesamt,
            "amortisationsinvestitionen_gesamt": round(amort_gesamt, 2),
            "einmalinvestitionen_gesamt": round(einmal_gesamt, 2),
            "capex_investitionen_gesamt": round(capex_gesamt, 2),
            "entwicklungsinvestitionen_gesamt": round(entwicklung_gesamt, 2),
            "amortisationsanteil_je_stueck": round(amort_anteil_summe, 2) if amort_anteil_summe else None,
            "investition_cost_total": fin_totals["cost_amount_total"],
            "investition_bottom_price_total": fin_totals["bottom_price_total"],
            "investition_revenue_total": fin_totals["revenue_amount_total"],
            "margin_revenue_minus_cost_total": fin_totals["margin_revenue_minus_cost_total"],
            "margin_revenue_minus_bottom_price_total": fin_totals[
                "margin_revenue_minus_bottom_price_total"
            ],
            "margin_bottom_price_minus_cost_total": fin_totals["margin_bottom_price_minus_cost_total"],
        },
        "parts": parts,
        "assemblies": assemblies,
        "investments": investments,
        "investments_capex": investments_capex,
        "investments_entwicklung": investments_entwicklung,
        "investments_other": investments_other,
        "sales_summary": sales_totals,
        "investment_summary": {
            "investitionen_gesamt": investitionen_gesamt,
            "amortisationsinvestitionen_gesamt": round(amort_gesamt, 2),
            "einmalinvestitionen_gesamt": round(einmal_gesamt, 2),
            "capex_investitionen_gesamt": round(capex_gesamt, 2),
            "entwicklungsinvestitionen_gesamt": round(entwicklung_gesamt, 2),
            "amortisationsanteil_je_stueck": round(amort_anteil_summe, 2) if amort_anteil_summe else None,
            "investition_cost_total": fin_totals["cost_amount_total"],
            "investition_bottom_price_total": fin_totals["bottom_price_total"],
            "investition_revenue_total": fin_totals["revenue_amount_total"],
            "margin_revenue_minus_cost_total": fin_totals["margin_revenue_minus_cost_total"],
            "margin_revenue_minus_bottom_price_total": fin_totals[
                "margin_revenue_minus_bottom_price_total"
            ],
            "margin_bottom_price_minus_cost_total": fin_totals["margin_bottom_price_minus_cost_total"],
            "capex": fin_capex,
            "entwicklung": fin_entwicklung,
            "legacy": fin_legacy,
            "material_assignments": investment_financial_summary["material_assignments"],
            "project_assignments": investment_financial_summary["project_assignments"],
        },
        "investment_financial_summary": investment_financial_summary,
        "kpi_summary": kpi_summary,
        "revenue_summary": {
            "hinweis": (
                "Einzelteile innerhalb von Baugruppen sind aus der Einzelteil-Liste "
                "und den Teilepreis-Summen ausgeschlossen. Teilepreise sind stückbezogen "
                "über die Projektstückzahl; Investitionsbeträge sind einmalig. "
                "Gesamtumsatz = Teileumsatz + Investitionserlöse (ohne CAPEX). "
                "CAPEX ist kapitalbindend, aber nicht EBIT-wirksam."
            ),
            "excluded_einzelteile_in_baugruppen": excluded_in_baugruppe_count,
        },
        "revenue_by_year": revenue_by_year,
    }

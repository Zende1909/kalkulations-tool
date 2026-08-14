"""Projektbezogene Business-Case-Gesamtübersicht."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.baugruppe import Baugruppe, BaugruppeKaufteilZuordnung, BaugruppeSpritzgussZuordnung, BaugruppeVeredelungZuordnung
from app.models.investition import Investition
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.services.dashboard import endpreis_aus_spritzguss, jahresumsatz_aus_baugruppe, preis_aus_baugruppe
from app.services.investition_service import EINMALZAHLUNG_HINWEIS, zuordnung_label


def _match_customer(row_customer: str, filter_customer: str) -> bool:
    return not filter_customer or (row_customer or "").strip() == filter_customer.strip()


def _match_project(row_project: str, filter_project: str) -> bool:
    return not filter_project or (row_project or "").strip() == filter_project.strip()


def build_project_business_case(
    db: Session,
    *,
    customer: str,
    project: str,
    calculation_id: int | None = None,
    baugruppe_id: int | None = None,
) -> dict:
    sg_rows = [
        r
        for r in db.scalars(select(SpritzgussKalkulation)).all()
        if _match_project(r.projekt, project) and _match_customer(r.kunde, customer)
    ]
    if calculation_id is not None:
        sg_rows = [r for r in sg_rows if r.id == calculation_id]

    bg_rows = [
        r
        for r in db.scalars(select(Baugruppe)).all()
        if _match_project(r.projekt, project) and _match_customer(r.kunde, customer)
    ]
    if baugruppe_id is not None:
        bg_rows = [r for r in bg_rows if r.id == baugruppe_id]

    inv_rows = [
        r
        for r in db.scalars(
            select(Investition).where(
                Investition.archived.is_(False),
                Investition.project_id == project,
            )
        ).all()
        if _match_customer(r.customer, customer)
    ]

    sg_map = {r.id: r for r in sg_rows}
    bg_map = {r.id: r for r in bg_rows}

    parts: list[dict] = []
    umsatz_einzelteile = 0.0
    for row in sg_rows:
        endpreis = endpreis_aus_spritzguss(row.ergebnis if isinstance(row.ergebnis, dict) else None)
        jahresumsatz = round(endpreis * row.jahresstueckzahl, 2) if endpreis and row.jahresstueckzahl else 0.0
        umsatz_einzelteile += jahresumsatz
        vd_count = db.scalar(
            select(func.count())
            .select_from(SpritzgussVeredelungZuordnung)
            .where(SpritzgussVeredelungZuordnung.kalkulation_id == row.id)
        ) or 0
        parts.append(
            {
                "id": row.id,
                "bezeichnung": row.teilebezeichnung,
                "teilenummer": row.teilenummer,
                "kunde": row.kunde,
                "projekt": row.projekt,
                "jahresstueckzahl": row.jahresstueckzahl,
                "endpreis_je_stueck": endpreis,
                "jahresumsatz": jahresumsatz,
                "anzahl_veredelungsschritte": int(vd_count),
            }
        )

    assemblies: list[dict] = []
    umsatz_baugruppen = 0.0
    for row in bg_rows:
        preis = preis_aus_baugruppe(row.ergebnis if isinstance(row.ergebnis, dict) else None)
        jahresumsatz = jahresumsatz_aus_baugruppe(
            row.ergebnis if isinstance(row.ergebnis, dict) else None,
            row.jahresstueckzahl,
        )
        umsatz_baugruppen += jahresumsatz
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
        assemblies.append(
            {
                "id": row.id,
                "name": row.name,
                "teilenummer": row.teilenummer,
                "kunde": row.kunde,
                "projekt": row.projekt,
                "jahresstueckzahl": row.jahresstueckzahl,
                "baugruppenpreis_je_stueck": preis,
                "jahresumsatz": jahresumsatz,
                "anzahl_einzelteile": int(sg_count),
                "anzahl_kaufteile": int(kt_count),
                "anzahl_veredelungsschritte": int(vd_count),
            }
        )

    investments: list[dict] = []
    amort_gesamt = 0.0
    einmal_gesamt = 0.0
    amort_anteil_summe = 0.0
    for inv in inv_rows:
        calc = sg_map.get(inv.calculation_id) if inv.calculation_id else None
        bg = bg_map.get(inv.baugruppe_id) if inv.baugruppe_id else None
        piece = float(inv.cost_per_piece) if inv.cost_per_piece is not None else None
        if inv.payment_type == "Amortisation":
            amort_gesamt += float(inv.amount)
            if piece is not None:
                amort_anteil_summe += piece
        else:
            einmal_gesamt += float(inv.amount)
        hint = EINMALZAHLUNG_HINWEIS if inv.payment_type == "Einmalzahlung" else ""
        investments.append(
            {
                "id": inv.id,
                "bezeichnung": inv.name or inv.description or inv.part_name,
                "investment_type": inv.investment_type,
                "payment_type": inv.payment_type,
                "amount": float(inv.amount),
                "amortization_volume": inv.amortization_volume,
                "cost_per_piece": piece,
                "zuordnung": zuordnung_label(
                    calculation_id=inv.calculation_id,
                    baugruppe_id=inv.baugruppe_id,
                    part_number=inv.part_number or "",
                    part_name=inv.part_name or "",
                    project_id=inv.project_id or "",
                    calc_teilenummer=calc.teilenummer if calc else None,
                    calc_bezeichnung=calc.teilebezeichnung if calc else None,
                    bg_name=bg.name if bg else None,
                    bg_teilenummer=bg.teilenummer if bg else None,
                ),
                "hinweis": hint,
                "bemerkung": inv.description or "",
            }
        )

    investitionen_gesamt = round(amort_gesamt + einmal_gesamt, 2)
    jahresstueckzahl_gesamt = sum(r.jahresstueckzahl for r in sg_rows) + sum(
        r.jahresstueckzahl for r in bg_rows
    )

    avg_teilepreis = None
    if parts:
        preise = [p["endpreis_je_stueck"] for p in parts if p["endpreis_je_stueck"] is not None]
        avg_teilepreis = round(sum(preise) / len(preise), 2) if preise else None

    avg_baugruppenpreis = None
    if assemblies:
        preise = [a["baugruppenpreis_je_stueck"] for a in assemblies if a["baugruppenpreis_je_stueck"] is not None]
        avg_baugruppenpreis = round(sum(preise) / len(preise), 2) if preise else None

    return {
        "project": project,
        "customer": customer,
        "kpis": {
            "kunde": customer,
            "projekt": project,
            "jahresstueckzahl_gesamt": jahresstueckzahl_gesamt,
            "umsatzpotenzial_einzelteile": round(umsatz_einzelteile, 2),
            "umsatzpotenzial_baugruppen": round(umsatz_baugruppen, 2),
            "anzahl_einzelteile": len(parts),
            "anzahl_baugruppen": len(assemblies),
            "anzahl_investitionen": len(investments),
            "investitionen_gesamt": investitionen_gesamt,
            "amortisationsinvestitionen_gesamt": round(amort_gesamt, 2),
            "einmalinvestitionen_gesamt": round(einmal_gesamt, 2),
            "amortisationsanteil_je_stueck": round(amort_anteil_summe, 2) if amort_anteil_summe else None,
            "teilepreis_je_stueck": avg_teilepreis,
            "baugruppenpreis_je_stueck": avg_baugruppenpreis,
        },
        "parts": parts,
        "assemblies": assemblies,
        "investments": investments,
        "investment_summary": {
            "investitionen_gesamt": investitionen_gesamt,
            "amortisationsinvestitionen_gesamt": round(amort_gesamt, 2),
            "einmalinvestitionen_gesamt": round(einmal_gesamt, 2),
            "amortisationsanteil_je_stueck": round(amort_anteil_summe, 2) if amort_anteil_summe else None,
            "einmalinvestitionen": [
                {"id": i["id"], "bezeichnung": i["bezeichnung"], "amount": i["amount"], "hinweis": i["hinweis"]}
                for i in investments
                if i["payment_type"] == "Einmalzahlung"
            ],
        },
        "revenue_summary": {
            "umsatzpotenzial_einzelteile": round(umsatz_einzelteile, 2),
            "umsatzpotenzial_baugruppen": round(umsatz_baugruppen, 2),
            "hinweis": "Einzelteil- und Baugruppenumsätze werden getrennt ausgewiesen und nicht addiert.",
        },
    }

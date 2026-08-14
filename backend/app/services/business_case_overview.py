"""Projektbezogene Business-Case-Gesamtübersicht."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.baugruppe import Baugruppe, BaugruppeKaufteilZuordnung, BaugruppeSpritzgussZuordnung, BaugruppeVeredelungZuordnung
from app.models.investition import Investition
from app.models.project import Project
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.models.spritzguss_veredelung_zuordnung import SpritzgussVeredelungZuordnung
from app.services.dashboard import endpreis_aus_spritzguss, jahresumsatz_aus_baugruppe, preis_aus_baugruppe
from app.services.investition_service import EINMALZAHLUNG_HINWEIS, zuordnung_label
from app.services.project_volume_service import build_project_volume_profile


def _match_customer(row_customer: str, filter_customer: str) -> bool:
    return not filter_customer or (row_customer or "").strip() == filter_customer.strip()


def _match_project(row_project: str, filter_project: str) -> bool:
    return not filter_project or (row_project or "").strip() == filter_project.strip()


def _find_project_entity(db: Session, project_name: str) -> Project | None:
    name = project_name.strip()
    if not name:
        return None
    return db.scalar(select(Project).where(Project.name == name).limit(1))


def _build_lifetime_yearly_rows(
    db: Session,
    *,
    project_entity: Project | None,
    teilepreis: float | None,
    baugruppenpreis: float | None = None,
    quantity_per_vehicle: float | None = None,
) -> tuple[list[dict], float, float]:
    """Liefert Jahreszeilen, Gesamtstückzahl und Umsatz über die Laufzeit."""
    if project_entity is None:
        return [], 0.0, 0.0

    profile = build_project_volume_profile(db, project_entity.id)
    qty = quantity_per_vehicle if quantity_per_vehicle is not None else profile["quantity_per_vehicle"]
    price = teilepreis if teilepreis is not None else baugruppenpreis

    rows: list[dict] = []
    total_volume = 0.0
    total_revenue = 0.0
    for row in profile["rows"]:
        project_volume = row["project_volume"]
        jahresumsatz = round(project_volume * price, 2) if price is not None else 0.0
        total_volume += project_volume
        total_revenue += jahresumsatz
        rows.append(
            {
                "calendar_year": row["calendar_year"],
                "vehicle_volume": row["vehicle_volume"],
                "quantity_per_vehicle": qty,
                "project_volume": project_volume,
                "teilepreis_je_stueck": teilepreis,
                "baugruppenpreis_je_stueck": baugruppenpreis,
                "jahresumsatz": jahresumsatz,
            }
        )

    return rows, round(total_volume, 2), round(total_revenue, 2)


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
    project_entity = _find_project_entity(db, project)

    parts: list[dict] = []
    umsatz_einzelteile = 0.0
    gesamtstueckzahl_laufzeit = 0.0
    for row in sg_rows:
        endpreis = endpreis_aus_spritzguss(row.ergebnis if isinstance(row.ergebnis, dict) else None)
        linked_project = db.get(Project, row.project_id) if getattr(row, "project_id", None) else project_entity
        yearly_rows, lifetime_volume, lifetime_revenue = _build_lifetime_yearly_rows(
            db,
            project_entity=linked_project,
            teilepreis=endpreis,
        )
        if yearly_rows:
            jahresumsatz = lifetime_revenue
            gesamtstueckzahl_laufzeit += lifetime_volume
        else:
            jahresumsatz = round(endpreis * row.jahresstueckzahl, 2) if endpreis and row.jahresstueckzahl else 0.0
            gesamtstueckzahl_laufzeit += row.jahresstueckzahl
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
                "gesamtstueckzahl_laufzeit": lifetime_volume if yearly_rows else row.jahresstueckzahl,
                "endpreis_je_stueck": endpreis,
                "jahresumsatz": jahresumsatz,
                "umsatzpotenzial_laufzeit": lifetime_revenue if yearly_rows else jahresumsatz,
                "lifetime_years": yearly_rows,
                "anzahl_veredelungsschritte": int(vd_count),
            }
        )

    assemblies: list[dict] = []
    umsatz_baugruppen = 0.0
    for row in bg_rows:
        preis = preis_aus_baugruppe(row.ergebnis if isinstance(row.ergebnis, dict) else None)
        yearly_rows, lifetime_volume, lifetime_revenue = _build_lifetime_yearly_rows(
            db,
            project_entity=project_entity,
            teilepreis=None,
            baugruppenpreis=preis,
            quantity_per_vehicle=getattr(row, "quantity_per_vehicle", None),
        )
        if yearly_rows and preis is not None:
            jahresumsatz = lifetime_revenue
        else:
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
                "gesamtstueckzahl_laufzeit": lifetime_volume if yearly_rows else row.jahresstueckzahl,
                "baugruppenpreis_je_stueck": preis,
                "jahresumsatz": jahresumsatz,
                "umsatzpotenzial_laufzeit": lifetime_revenue if yearly_rows else jahresumsatz,
                "lifetime_years": yearly_rows,
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

    project_lifetime_profile: list[dict] = []
    umsatz_je_jahr: dict[int, float] = {}
    if project_entity is not None:
        profile = build_project_volume_profile(db, project_entity.id)
        avg_teilepreis_for_profile = None
        preise = [p["endpreis_je_stueck"] for p in parts if p["endpreis_je_stueck"] is not None]
        if preise:
            avg_teilepreis_for_profile = sum(preise) / len(preise)
        for row in profile["rows"]:
            jahresumsatz = (
                round(row["project_volume"] * avg_teilepreis_for_profile, 2)
                if avg_teilepreis_for_profile is not None
                else 0.0
            )
            umsatz_je_jahr[row["calendar_year"]] = umsatz_je_jahr.get(row["calendar_year"], 0.0) + jahresumsatz
            project_lifetime_profile.append(
                {
                    "calendar_year": row["calendar_year"],
                    "vehicle_volume": row["vehicle_volume"],
                    "quantity_per_vehicle": row["quantity_per_vehicle"],
                    "project_volume": row["project_volume"],
                    "teilepreis_je_stueck": round(avg_teilepreis_for_profile, 2) if avg_teilepreis_for_profile else None,
                    "jahresumsatz": jahresumsatz,
                }
            )

    umsatzpotenzial_laufzeit = round(umsatz_einzelteile + umsatz_baugruppen, 2)

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
            "gesamtstueckzahl_laufzeit": round(gesamtstueckzahl_laufzeit, 2),
            "umsatzpotenzial_laufzeit": umsatzpotenzial_laufzeit,
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
            "umsatzpotenzial_laufzeit": umsatzpotenzial_laufzeit,
            "umsatz_je_kalenderjahr": [
                {"calendar_year": year, "jahresumsatz": round(amount, 2)}
                for year, amount in sorted(umsatz_je_jahr.items())
            ],
            "hinweis": "Einzelteil- und Baugruppenumsätze werden getrennt ausgewiesen und nicht addiert.",
        },
        "lifetime_volume_profile": project_lifetime_profile,
    }

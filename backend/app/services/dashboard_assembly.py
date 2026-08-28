"""Lese-Übersicht einer Baugruppe für Dashboard und Export – keine Neuberechnung."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.assembly_position import AssemblyPosition
from app.models.baugruppe import Baugruppe
from app.models.investition import Investition
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.services.dashboard import (
    cost_structure_from_ergebnis,
    jahresumsatz_aus_baugruppe,
    parse_json_dict,
    preis_aus_baugruppe,
)
from app.services.investition_financials import effective_cost_amount, financial_fields_for_export


def _money(value: object) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _optional_money(value: object) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _component_costs(ergebnis: dict) -> dict[str, float]:
    positions = ergebnis.get("positions") or []
    einzelteile = 0.0
    kaufteile = 0.0
    veredelung = 0.0
    if isinstance(positions, list) and positions:
        for pos in positions:
            if not isinstance(pos, dict):
                continue
            amount = _money(pos.get("zwischensumme"))
            ptype = pos.get("position_type")
            if ptype == "PURCHASED_PART":
                kaufteile += amount
            elif ptype == "PROCESS":
                veredelung += amount
            else:
                einzelteile += amount
    else:
        einzelteile = _money(ergebnis.get("einzelteile_gesamt"))
        kaufteile = _money(ergebnis.get("kaufteile_gesamt"))
        veredelung = _money(ergebnis.get("veredelung_gesamt"))
    return {
        "einzelteilkosten": round(einzelteile, 2),
        "kaufteilkosten": round(kaufteile, 2),
        "veredelungskosten": round(veredelung, 2),
    }


def _bom_from_ergebnis(ergebnis: dict) -> list[dict]:
    rows: list[dict] = []
    positions = ergebnis.get("positions") or []
    if isinstance(positions, list) and positions:
        for pos in sorted(
            (p for p in positions if isinstance(p, dict)),
            key=lambda p: int(p.get("sequence") or 0),
        ):
            rows.append(
                {
                    "position_type": pos.get("position_type") or "",
                    "bezeichnung": pos.get("name_snapshot") or pos.get("label") or "",
                    "teilenummer": pos.get("part_number_snapshot") or "",
                    "menge": pos.get("quantity") or 0,
                    "mengenfaktor": pos.get("quantity_factor") or 1,
                    "einzelpreis": _optional_money(pos.get("einzelpreis")),
                    "zwischensumme": _optional_money(pos.get("zwischensumme")),
                }
            )
        return rows

    mapping = (
        ("einzelteile", "PART"),
        ("kaufteile", "PURCHASED_PART"),
        ("veredelungen", "PROCESS"),
    )
    for key, ptype in mapping:
        for pos in ergebnis.get(key) or []:
            if not isinstance(pos, dict):
                continue
            detail = pos.get("detail") if isinstance(pos.get("detail"), dict) else {}
            rows.append(
                {
                    "position_type": ptype,
                    "bezeichnung": pos.get("bezeichnung") or "",
                    "teilenummer": detail.get("teilenummer") or "",
                    "menge": pos.get("menge") or pos.get("mengenfaktor") or 0,
                    "mengenfaktor": pos.get("mengenfaktor") or 1,
                    "einzelpreis": _optional_money(
                        pos.get("einzelpreis") or pos.get("kosten_je_stueck")
                    ),
                    "zwischensumme": _optional_money(pos.get("zwischensumme")),
                }
            )
    return rows


def _bom_from_positions(positions: list[AssemblyPosition]) -> list[dict]:
    rows: list[dict] = []
    for pos in sorted(positions, key=lambda p: p.sequence):
        rows.append(
            {
                "position_type": pos.position_type,
                "bezeichnung": pos.name_snapshot or pos.label or "",
                "teilenummer": pos.part_number_snapshot or "",
                "menge": pos.quantity,
                "mengenfaktor": pos.quantity_factor,
                "einzelpreis": _optional_money(pos.cost_snapshot or pos.price_snapshot),
                "zwischensumme": None,
            }
        )
    return rows


def _markup_rows(ergebnis: dict) -> list[dict]:
    herstellkosten = _optional_money(ergebnis.get("herstellkosten"))
    vvgk = _optional_money(ergebnis.get("vvgk"))
    gewinn = _optional_money(ergebnis.get("gewinn"))
    skonto = _optional_money(ergebnis.get("skonto"))
    selbstkosten = _optional_money(ergebnis.get("selbstkosten"))
    netto = _optional_money(ergebnis.get("nettoverkaufspreis"))

    def pct(amount: float | None, base: float | None) -> float | None:
        if amount is None or base in (None, 0):
            return 0.0 if amount == 0 else None
        return round(amount / base * 100, 2)

    rows = [
        {
            "typ": "vvgk",
            "bezeichnung": "VVGK",
            "betrag": vvgk,
            "satz_prozent": pct(vvgk, herstellkosten),
        },
        {
            "typ": "gewinn",
            "bezeichnung": "Gewinn",
            "betrag": gewinn,
            "satz_prozent": pct(gewinn, selbstkosten),
        },
        {
            "typ": "skonto",
            "bezeichnung": "Skonto",
            "betrag": skonto if skonto is not None else (0.0 if "skonto" in ergebnis else None),
            "satz_prozent": pct(
                skonto if skonto is not None else (0.0 if "skonto" in ergebnis else None),
                netto,
            ),
        },
    ]
    return rows


def build_assembly_overview(db: Session, assembly_id: int) -> dict:
    obj = db.get(Baugruppe, assembly_id)
    if not obj:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baugruppe nicht gefunden")

    ergebnis = parse_json_dict(obj.ergebnis) or {}
    positions = list(
        db.scalars(
            select(AssemblyPosition)
            .where(AssemblyPosition.parent_assembly_id == assembly_id)
            .where(AssemblyPosition.active.is_(True))
        ).all()
    )
    part_ids = [p.part_calculation_id for p in positions if p.part_calculation_id]
    sg_rows = []
    if part_ids:
        sg_rows = list(
            db.scalars(
                select(SpritzgussKalkulation).where(SpritzgussKalkulation.id.in_(part_ids))
            ).all()
        )
    sg_ergebnisse = [parse_json_dict(row.ergebnis) for row in sg_rows]

    conditions = [Investition.baugruppe_id == assembly_id]
    if part_ids:
        conditions.append(Investition.calculation_id.in_(part_ids))
    inv_rows = list(db.scalars(select(Investition).where(or_(*conditions))).all())
    werkzeugkosten = round(
        sum(
            effective_cost_amount(
                cost_amount=getattr(inv, "cost_amount", None),
                amount=inv.amount,
            )
            for inv in inv_rows
        ),
        2,
    )
    costs = _component_costs(ergebnis) if ergebnis else {
        "einzelteilkosten": 0.0,
        "kaufteilkosten": 0.0,
        "veredelungskosten": 0.0,
    }
    bom = _bom_from_ergebnis(ergebnis) if ergebnis else _bom_from_positions(positions)
    vvgk = _optional_money(ergebnis.get("vvgk"))
    gewinn = _optional_money(ergebnis.get("gewinn"))
    skonto = _optional_money(ergebnis.get("skonto"))
    if "skonto" in ergebnis and skonto is None:
        skonto = 0.0
    netto = _optional_money(ergebnis.get("nettoverkaufspreis"))
    brutto = preis_aus_baugruppe(ergebnis) if ergebnis else None
    herstellkosten = _optional_money(ergebnis.get("herstellkosten"))
    jahresumsatz = jahresumsatz_aus_baugruppe(ergebnis, obj.jahresstueckzahl)
    gesamtsumme = brutto
    if brutto is not None and obj.jahresstueckzahl:
        gesamtsumme = round(brutto * obj.jahresstueckzahl, 2)

    return {
        "id": obj.id,
        "name": obj.name,
        "teilenummer": obj.teilenummer,
        "kunde": obj.kunde,
        "projekt": obj.projekt,
        "status": obj.status,
        "structure_version": obj.structure_version,
        "assembly_type": obj.assembly_type,
        "jahresstueckzahl": obj.jahresstueckzahl,
        "letzte_kalkulation": obj.updated_at,
        "bom": bom,
        "einzelteilkosten": costs["einzelteilkosten"],
        "kaufteilkosten": costs["kaufteilkosten"],
        "veredelungskosten": costs["veredelungskosten"],
        "investitionskosten": werkzeugkosten,
        "vvgk": vvgk,
        "gewinn": gewinn,
        "skonto": skonto,
        "nettoverkaufspreis": netto,
        "bruttoverkaufspreis": brutto,
        "preis_je_stueck": brutto,
        "herstellkosten": herstellkosten,
        "jahresumsatz": jahresumsatz,
        "gesamtsumme": gesamtsumme,
        "zuschlagssaetze": _markup_rows(ergebnis) if ergebnis else [],
        "cost_structure": cost_structure_from_ergebnis(
            ergebnis,
            investitionen_betrag=werkzeugkosten,
            spritzguss_ergebnisse=sg_ergebnisse,
        ),
        "investitionen": [
            {
                "id": inv.id,
                "bezeichnung": inv.name or inv.description or inv.part_name,
                "typ": inv.investment_type,
                "betrag": effective_cost_amount(
                    cost_amount=getattr(inv, "cost_amount", None),
                    amount=inv.amount,
                ),
                **financial_fields_for_export(
                    cost_amount=getattr(inv, "cost_amount", None),
                    bottom_price=getattr(inv, "bottom_price", None),
                    revenue_amount=getattr(inv, "revenue_amount", None),
                    legacy_amount=inv.amount,
                ),
                "status": inv.status,
            }
            for inv in inv_rows
        ],
        "has_result": bool(ergebnis),
        "generated_at": datetime.now(timezone.utc),
    }

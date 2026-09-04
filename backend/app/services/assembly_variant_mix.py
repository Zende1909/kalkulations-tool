"""Projektbezogene Baugruppenanteile (Variantenmix) – Mengen- und Kostenaggregation.

Fachlich: Ausführungen = normale Baugruppen mit ``variant_share_pct`` („Anteil am Projekt (%)“)
innerhalb desselben ``project_id``. ``assembly_families`` / ``family_id`` sind Legacy.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.models.baugruppe import (
    Baugruppe,
    BaugruppeKaufteilZuordnung,
    BaugruppeSpritzgussZuordnung,
    BaugruppeVeredelungZuordnung,
)
from app.models.spritzguss_kalkulation import SpritzgussKalkulation
from app.services.project_volume_service import average_jahresstueckzahl_for_project

SHARE_SUM_TOLERANCE = Decimal("0.05")
MIX_COMPLETE = "complete"
MIX_INCOMPLETE = "incomplete"
MIX_OVERFLOW = "overflow"
MIX_EMPTY = "empty"


@dataclass(frozen=True)
class ShareValidation:
    status: str
    active_share_sum_pct: float
    missing_pct: float
    overflow_pct: float
    message: str
    is_complete: bool
    can_compute_full: bool


def validate_share_pct(value: float | int | Decimal | None) -> float:
    if value is None:
        raise ValueError("Anteil am Projekt ist erforderlich.")
    pct = float(value)
    if not math.isfinite(pct):
        raise ValueError("Anteil am Projekt ist ungültig.")
    if pct < 0:
        raise ValueError("Anteil am Projekt darf nicht unter 0 % liegen.")
    if pct > 100:
        raise ValueError("Anteil am Projekt darf nicht über 100 % liegen.")
    return pct


def validate_active_share_sum(active_shares: list[float]) -> ShareValidation:
    total = sum(Decimal(str(s)) for s in active_shares)
    total_f = float(total)
    if not active_shares:
        return ShareValidation(
            status=MIX_EMPTY,
            active_share_sum_pct=0.0,
            missing_pct=100.0,
            overflow_pct=0.0,
            message="Es sind noch keine aktiven Baugruppenanteile im Projektmix erfasst.",
            is_complete=False,
            can_compute_full=False,
        )
    delta = total - Decimal("100")
    if abs(delta) <= SHARE_SUM_TOLERANCE:
        return ShareValidation(
            status=MIX_COMPLETE,
            active_share_sum_pct=total_f,
            missing_pct=0.0,
            overflow_pct=0.0,
            message="Die aktiven Baugruppenanteile ergeben innerhalb dieses Projekts zusammen 100 %.",
            is_complete=True,
            can_compute_full=True,
        )
    if delta < 0:
        missing = float(Decimal("100") - total)
        return ShareValidation(
            status=MIX_INCOMPLETE,
            active_share_sum_pct=total_f,
            missing_pct=missing,
            overflow_pct=0.0,
            message=(
                "Die aktiven Baugruppenanteile müssen innerhalb dieses Projekts zusammen 100 % ergeben. "
                f"Aktuell sind {total_f:g} % erfasst. Es fehlen {missing:g} %. "
                "Der Variantenmix ist für eine vollständige Baugruppenberechnung noch nicht vollständig."
            ),
            is_complete=False,
            can_compute_full=False,
        )
    overflow = float(delta)
    return ShareValidation(
        status=MIX_OVERFLOW,
        active_share_sum_pct=total_f,
        missing_pct=0.0,
        overflow_pct=overflow,
        message=(
            "Die aktiven Baugruppenanteile überschreiten zusammen 100 %. "
            f"Aktuell sind {total_f:g} % erfasst (überschüssig {overflow:g} %)."
        ),
        is_complete=False,
        can_compute_full=False,
    )


def variant_jahresmenge(project_jahresstueckzahl: int, share_pct: float) -> int:
    if project_jahresstueckzahl < 0:
        project_jahresstueckzahl = 0
    qty = project_jahresstueckzahl * float(share_pct) / 100.0
    if not math.isfinite(qty) or qty <= 0:
        return 0
    return int(round(qty))


def effective_component_jahresmenge(variant_jahresmenge_value: int, menge_je_variante: float) -> float:
    if variant_jahresmenge_value <= 0 or menge_je_variante <= 0:
        return 0.0
    return float(variant_jahresmenge_value) * float(menge_je_variante)


def lose_from_jahresmenge(jahresmenge: float, losgroesse: int | None) -> int | None:
    """Bestehende Losgrößenlogik nur anwenden, wenn Losgröße > 0 vorhanden ist."""
    if losgroesse is None or losgroesse <= 0:
        return None
    if jahresmenge <= 0:
        return 0
    return int(math.ceil(float(jahresmenge) / float(losgroesse)))


def project_jahresstueckzahl(db: Session, project_id: int) -> int:
    avg = average_jahresstueckzahl_for_project(db, project_id)
    if avg.has_volumes and avg.jahresstueckzahl is not None:
        return int(avg.jahresstueckzahl)
    return 0


def participates_in_project_mix(baugruppe: Baugruppe) -> bool:
    """Baugruppe nimmt am Variantenmix teil, wenn ein Projektanteil gesetzt ist."""
    return baugruppe.variant_share_pct is not None


def active_mix_participants(baugruppen: list[Baugruppe]) -> list[Baugruppe]:
    return [
        b
        for b in baugruppen
        if b.aktiv
        and b.assembly_type == "TOP_LEVEL"
        and participates_in_project_mix(b)
    ]


def list_project_baugruppen(db: Session, project_id: int) -> list[Baugruppe]:
    return list(
        db.scalars(
            select(Baugruppe)
            .where(
                or_(
                    Baugruppe.project_id == project_id,
                    Baugruppe.linked_project_id == project_id,
                )
            )
            .options(selectinload(Baugruppe.assembly_positions))
            .order_by(Baugruppe.id)
        ).all()
    )


def apply_share_to_jahresstueckzahl(
    *,
    project_qty: int,
    share_pct: float | None,
    legacy_full_project_qty: int | None = None,
) -> int:
    """Ableitung der Baugruppen-Jahresmenge.

    Mit Anteil: Projektstückzahl × Anteil/100.
    Ohne Anteil (Legacy): volle Projektstückzahl bzw. bestehender Fallback.
    """
    if share_pct is not None:
        return variant_jahresmenge(project_qty, float(share_pct))
    if legacy_full_project_qty is not None:
        return int(legacy_full_project_qty)
    return int(project_qty)


def _component_rows_for_baugruppe(
    db: Session,
    baugruppe: Baugruppe,
    v_qty: int,
    component_totals: dict[tuple[str, int], dict[str, Any]],
) -> list[dict[str, Any]]:
    components: list[dict[str, Any]] = []

    sg_rows = list(
        db.scalars(
            select(BaugruppeSpritzgussZuordnung).where(
                BaugruppeSpritzgussZuordnung.baugruppe_id == baugruppe.id
            )
        ).all()
    )
    kt_rows = list(
        db.scalars(
            select(BaugruppeKaufteilZuordnung).where(
                BaugruppeKaufteilZuordnung.baugruppe_id == baugruppe.id
            )
        ).all()
    )
    ve_rows = list(
        db.scalars(
            select(BaugruppeVeredelungZuordnung).where(
                BaugruppeVeredelungZuordnung.baugruppe_id == baugruppe.id
            )
        ).all()
    )

    for row in sg_rows:
        eff = effective_component_jahresmenge(v_qty, float(row.menge))
        components.append(
            {
                "component_type": "PART",
                "component_id": row.spritzguss_kalkulation_id,
                "bezeichnung": row.snapshot_bezeichnung,
                "teilenummer": row.snapshot_teilenummer,
                "menge_je_variante": float(row.menge),
                "effektive_jahresmenge": eff,
            }
        )
        key = ("PART", int(row.spritzguss_kalkulation_id))
        agg = component_totals.setdefault(
            key,
            {
                "component_type": "PART",
                "component_id": int(row.spritzguss_kalkulation_id),
                "bezeichnung": row.snapshot_bezeichnung,
                "teilenummer": row.snapshot_teilenummer,
                "effektive_jahresmenge": 0.0,
                "losgroesse": None,
                "anzahl_lose": None,
            },
        )
        agg["effektive_jahresmenge"] = float(agg["effektive_jahresmenge"]) + eff

    for row in kt_rows:
        eff = effective_component_jahresmenge(v_qty, float(row.menge))
        components.append(
            {
                "component_type": "PURCHASED_PART",
                "component_id": row.kaufteil_id,
                "bezeichnung": row.snapshot_bezeichnung,
                "teilenummer": "",
                "menge_je_variante": float(row.menge),
                "effektive_jahresmenge": eff,
            }
        )
        key = ("PURCHASED_PART", int(row.kaufteil_id))
        agg = component_totals.setdefault(
            key,
            {
                "component_type": "PURCHASED_PART",
                "component_id": int(row.kaufteil_id),
                "bezeichnung": row.snapshot_bezeichnung,
                "teilenummer": "",
                "effektive_jahresmenge": 0.0,
            },
        )
        agg["effektive_jahresmenge"] = float(agg["effektive_jahresmenge"]) + eff

    for row in ve_rows:
        components.append(
            {
                "component_type": "PROCESS",
                "component_id": row.veredelungsschritt_id,
                "bezeichnung": row.snapshot_bezeichnung,
                "teilenummer": "",
                "menge_je_variante": float(row.mengenfaktor),
                "effektive_jahresmenge": effective_component_jahresmenge(
                    v_qty, float(row.mengenfaktor)
                ),
            }
        )

    return components


def _enrich_part_lot_sizes(db: Session, component_totals: dict[tuple[str, int], dict[str, Any]]) -> None:
    for key, agg in component_totals.items():
        if key[0] != "PART":
            continue
        calc = db.get(SpritzgussKalkulation, key[1])
        if calc is None:
            continue
        los = int(calc.losgroesse or 0) if getattr(calc, "losgroesse", None) else 0
        agg["losgroesse"] = los if los > 0 else None
        agg["anzahl_lose"] = lose_from_jahresmenge(
            float(agg["effektive_jahresmenge"]),
            los if los > 0 else None,
        )


def _build_mix_from_baugruppen(
    db: Session,
    *,
    project_id: int,
    baugruppen: list[Baugruppe],
    meta: dict[str, Any],
) -> dict[str, Any]:
    project_qty = project_jahresstueckzahl(db, project_id)
    participants = active_mix_participants(baugruppen)
    shares = [float(b.variant_share_pct or 0) for b in participants]
    validation = validate_active_share_sum(shares)

    rows: list[dict[str, Any]] = []
    component_totals: dict[tuple[str, int], dict[str, Any]] = {}
    weighted_cost_sum = 0.0

    for b in baugruppen:
        in_mix = participates_in_project_mix(b)
        share = float(b.variant_share_pct or 0) if (b.aktiv and in_mix) else 0.0
        if b.aktiv and in_mix:
            v_qty = variant_jahresmenge(project_qty, share)
        elif b.aktiv and not in_mix:
            # Legacy ohne Mix: volle Projektstückzahl (bestehendes Verhalten)
            v_qty = int(b.jahresstueckzahl or project_qty)
        else:
            v_qty = 0

        ergebnis = b.ergebnis if isinstance(b.ergebnis, dict) else {}
        unit_cost = float(ergebnis.get("baugruppenpreis_je_stueck") or 0)
        weighted_contrib = unit_cost * (share / 100.0) if (b.aktiv and in_mix) else 0.0
        if b.aktiv and in_mix and validation.can_compute_full:
            weighted_cost_sum += weighted_contrib

        components = _component_rows_for_baugruppe(db, b, v_qty, component_totals)
        rows.append(
            {
                "id": b.id,
                "teilenummer": b.teilenummer,
                "bezeichnung": b.name,
                "anteil_prozent": float(b.variant_share_pct) if b.variant_share_pct is not None else None,
                "aktiv": bool(b.aktiv),
                "jahresmenge": v_qty,
                "komponenten_anzahl": len(components),
                "kosten_je_stueck": unit_cost,
                "gewichteter_kostenbeitrag": (
                    weighted_contrib if (in_mix and validation.can_compute_full) else None
                ),
                "komponenten": components,
                "legacy_standalone": not in_mix,
                "in_project_mix": in_mix,
            }
        )

    _enrich_part_lot_sizes(db, component_totals)

    return {
        **meta,
        "project_id": project_id,
        "project_jahresstueckzahl": project_qty,
        "mix_status": validation.status,
        "mix_message": validation.message,
        "mix_is_complete": validation.is_complete,
        "can_compute_full": validation.can_compute_full,
        "active_share_sum_pct": validation.active_share_sum_pct,
        "missing_pct": validation.missing_pct,
        "overflow_pct": validation.overflow_pct,
        "baugruppen": rows,
        # Alias für Legacy-Familien-API
        "variants": rows,
        "aggregated_components": list(component_totals.values()),
        "gewichtete_kosten_pro_projektstueck": (
            round(weighted_cost_sum, 6) if validation.can_compute_full else None
        ),
    }


def build_project_mix_result(db: Session, project_id: int) -> dict[str, Any]:
    """Aktiver Variantenmix: alle Baugruppen eines Projekts mit optionalem Anteil."""
    from app.models.project import Project

    project = db.get(Project, project_id)
    if project is None:
        raise ValueError("Projekt nicht gefunden.")

    baugruppen = list_project_baugruppen(db, project_id)
    return _build_mix_from_baugruppen(
        db,
        project_id=project_id,
        baugruppen=baugruppen,
        meta={
            "name": project.name,
            "status": "aktiv" if project.active else "inaktiv",
            "aktiv": bool(project.active),
            "family_id": None,
        },
    )


def build_family_mix_result(db: Session, family_id: int) -> dict[str, Any]:
    """Legacy: Mix über family_id – fachlich abgelöst durch build_project_mix_result."""
    from app.models.assembly_family import AssemblyFamily

    family = db.get(AssemblyFamily, family_id)
    if family is None:
        raise ValueError("Baugruppenfamilie nicht gefunden.")

    variants = list(
        db.scalars(
            select(Baugruppe)
            .where(Baugruppe.family_id == family_id)
            .options(selectinload(Baugruppe.assembly_positions))
            .order_by(Baugruppe.id)
        ).all()
    )
    return _build_mix_from_baugruppen(
        db,
        project_id=int(family.project_id),
        baugruppen=variants,
        meta={
            "family_id": family.id,
            "name": family.name,
            "status": family.status,
            "aktiv": family.aktiv,
        },
    )


# Rückwärtskompatible Aliase
active_variants = active_mix_participants


def assert_unique_teilenummer(
    db: Session,
    family_id: int,
    teilenummer: str,
    *,
    exclude_variant_id: int | None = None,
) -> None:
    """Legacy-Familien-API: Eindeutigkeit innerhalb einer Familie."""
    from sqlalchemy import func

    tn = (teilenummer or "").strip()
    if not tn:
        raise ValueError("Teilenummer ist erforderlich.")
    stmt = select(Baugruppe).where(
        Baugruppe.family_id == family_id,
        func.lower(Baugruppe.teilenummer) == tn.lower(),
    )
    if exclude_variant_id is not None:
        stmt = stmt.where(Baugruppe.id != exclude_variant_id)
    existing = db.scalars(stmt).first()
    if existing is not None:
        raise ValueError("Die Teilenummer ist innerhalb dieser Baugruppenfamilie bereits vergeben.")

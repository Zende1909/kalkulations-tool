"""Dashboard-Aggregation aus gespeicherten Kalkulationsdaten."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean


@dataclass(frozen=True)
class SpritzgussRecord:
    id: int
    teilebezeichnung: str
    teilenummer: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    aktiv: bool
    ergebnis: dict | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class BaugruppeRecord:
    id: int
    name: str
    teilenummer: str
    kunde: str
    projekt: str
    jahresstueckzahl: int
    aktiv: bool
    ergebnis: dict | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class InvestitionRecord:
    id: int
    project_id: str
    calculation_id: int | None
    baugruppe_id: int | None
    part_name: str
    description: str
    amount: float
    investment_type: str
    payment_type: str
    status: str
    kunde: str = ""
    projekt: str = ""


def endpreis_aus_spritzguss(ergebnis: dict | None) -> float | None:
    """Gespeicherter Endpreis je Stück inkl. Veredelung – keine Doppelzählung."""
    if not isinstance(ergebnis, dict):
        return None
    preis = ergebnis.get("endpreis_je_stueck")
    if preis is None:
        preis = ergebnis.get("verkaufspreis")
    if preis is None:
        return None
    try:
        value = float(preis)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def preis_aus_baugruppe(ergebnis: dict | None) -> float | None:
    if not isinstance(ergebnis, dict):
        return None
    preis = ergebnis.get("baugruppenpreis_je_stueck")
    if preis is None:
        return None
    try:
        value = float(preis)
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def jahresumsatz_aus_baugruppe(ergebnis: dict | None, jahresstueckzahl: int) -> float:
    if isinstance(ergebnis, dict):
        umsatz = ergebnis.get("jahresumsatz")
        if umsatz is not None:
            try:
                return max(float(umsatz), 0.0)
            except (TypeError, ValueError):
                pass
        preis = preis_aus_baugruppe(ergebnis)
        if preis is not None:
            return round(preis * max(jahresstueckzahl, 0), 2)
    return 0.0


def _matches(value: str, filter_value: str | None) -> bool:
    if not filter_value:
        return True
    return value.strip().casefold() == filter_value.strip().casefold()


def _filter_spritzguss(
    rows: list[SpritzgussRecord],
    *,
    project: str | None,
    customer: str | None,
) -> list[SpritzgussRecord]:
    return [
        r
        for r in rows
        if r.aktiv and _matches(r.projekt, project) and _matches(r.kunde, customer)
    ]


def _filter_baugruppen(
    rows: list[BaugruppeRecord],
    *,
    project: str | None,
    customer: str | None,
) -> list[BaugruppeRecord]:
    return [
        r
        for r in rows
        if r.aktiv and _matches(r.projekt, project) and _matches(r.kunde, customer)
    ]


def _filter_investitionen(
    rows: list[InvestitionRecord],
    *,
    project: str | None,
    customer: str | None,
) -> list[InvestitionRecord]:
    result: list[InvestitionRecord] = []
    for row in rows:
        projekt = row.projekt or row.project_id
        if not _matches(projekt, project):
            continue
        if not _matches(row.kunde, customer):
            continue
        result.append(row)
    return result


def build_filter_options(
    spritzguss_rows: list[SpritzgussRecord],
    baugruppe_rows: list[BaugruppeRecord],
) -> dict[str, list[str]]:
    projekte: set[str] = set()
    kunden: set[str] = set()
    for row in spritzguss_rows:
        if not row.aktiv:
            continue
        if row.projekt.strip():
            projekte.add(row.projekt.strip())
        if row.kunde.strip():
            kunden.add(row.kunde.strip())
    for row in baugruppe_rows:
        if not row.aktiv:
            continue
        if row.projekt.strip():
            projekte.add(row.projekt.strip())
        if row.kunde.strip():
            kunden.add(row.kunde.strip())
    return {
        "projekte": sorted(projekte, key=str.casefold),
        "kunden": sorted(kunden, key=str.casefold),
    }


def build_dashboard_summary(
    spritzguss_rows: list[SpritzgussRecord],
    baugruppe_rows: list[BaugruppeRecord],
    investition_rows: list[InvestitionRecord],
    *,
    project: str | None = None,
    customer: str | None = None,
) -> dict:
    filter_options = build_filter_options(spritzguss_rows, baugruppe_rows)

    sg = _filter_spritzguss(spritzguss_rows, project=project, customer=customer)
    bg = _filter_baugruppen(baugruppe_rows, project=project, customer=customer)
    inv = _filter_investitionen(investition_rows, project=project, customer=customer)

    projekte_set: set[str] = set()
    for row in sg:
        if row.projekt.strip():
            projekte_set.add(row.projekt.strip())
    for row in bg:
        if row.projekt.strip():
            projekte_set.add(row.projekt.strip())

    sg_preise = [p for r in sg if (p := endpreis_aus_spritzguss(r.ergebnis)) is not None]
    bg_preise = [p for r in bg if (p := preis_aus_baugruppe(r.ergebnis)) is not None]

    jahresstueckzahl = sum(r.jahresstueckzahl for r in sg) + sum(r.jahresstueckzahl for r in bg)
    umsatzpotenzial = sum(jahresumsatz_aus_baugruppe(r.ergebnis, r.jahresstueckzahl) for r in bg)
    for row in sg:
        preis = endpreis_aus_spritzguss(row.ergebnis)
        if preis is not None and row.jahresstueckzahl > 0:
            umsatzpotenzial += round(preis * row.jahresstueckzahl, 2)

    recent: list[dict] = []
    for row in sg:
        recent.append(
            {
                "id": row.id,
                "kalkulationsart": "Spritzguss",
                "bezeichnung": row.teilebezeichnung,
                "nummer": row.teilenummer,
                "kunde": row.kunde,
                "projekt": row.projekt,
                "endpreis_je_stueck": endpreis_aus_spritzguss(row.ergebnis),
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )
    for row in bg:
        recent.append(
            {
                "id": row.id,
                "kalkulationsart": "Baugruppe",
                "bezeichnung": row.name,
                "nummer": row.teilenummer,
                "kunde": row.kunde,
                "projekt": row.projekt,
                "endpreis_je_stueck": preis_aus_baugruppe(row.ergebnis),
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
        )
    recent.sort(key=lambda x: x["updated_at"], reverse=True)
    recent = recent[:20]

    assemblies = [
        {
            "id": row.id,
            "name": row.name,
            "teilenummer": row.teilenummer,
            "kunde": row.kunde,
            "projekt": row.projekt,
            "preis_je_stueck": preis_aus_baugruppe(row.ergebnis),
            "jahresstueckzahl": row.jahresstueckzahl,
            "jahresumsatz": jahresumsatz_aus_baugruppe(row.ergebnis, row.jahresstueckzahl),
        }
        for row in sorted(bg, key=lambda r: r.updated_at, reverse=True)
    ]

    investments = []
    for row in inv:
        einmal = row.payment_type.casefold() == "einmalzahlung"
        investments.append(
            {
                "id": row.id,
                "bezeichnung": row.description or row.part_name,
                "typ": row.investment_type,
                "betrag": float(row.amount),
                "projekt": row.projekt or row.project_id,
                "kunde": row.kunde,
                "status": row.status,
                "im_stueckpreis": False,
                "hinweis": (
                    "Separat, nicht im Stückpreis enthalten"
                    if einmal
                    else "Separat ausgewiesen"
                ),
            }
        )

    price_items: list[dict] = []
    for row in sg:
        preis = endpreis_aus_spritzguss(row.ergebnis)
        if preis is not None:
            price_items.append(
                {
                    "label": f"{row.teilebezeichnung} ({row.teilenummer})",
                    "value": preis,
                    "typ": "Spritzguss",
                }
            )
    for row in bg:
        preis = preis_aus_baugruppe(row.ergebnis)
        if preis is not None:
            price_items.append(
                {
                    "label": f"{row.name} ({row.teilenummer})",
                    "value": preis,
                    "typ": "Baugruppe",
                }
            )
    price_items.sort(key=lambda x: x["value"], reverse=True)
    price_comparison = price_items[:10]

    inv_by_project: dict[str, float] = {}
    for row in inv:
        key = (row.projekt or row.project_id or "Ohne Projekt").strip() or "Ohne Projekt"
        inv_by_project[key] = inv_by_project.get(key, 0.0) + float(row.amount)

    rev_by_project: dict[str, float] = {}
    for row in bg:
        key = row.projekt.strip() or "Ohne Projekt"
        rev_by_project[key] = rev_by_project.get(key, 0.0) + jahresumsatz_aus_baugruppe(
            row.ergebnis, row.jahresstueckzahl
        )
    for row in sg:
        preis = endpreis_aus_spritzguss(row.ergebnis)
        if preis is not None and row.jahresstueckzahl > 0:
            key = row.projekt.strip() or "Ohne Projekt"
            rev_by_project[key] = rev_by_project.get(key, 0.0) + round(
                preis * row.jahresstueckzahl, 2
            )

    return {
        "kpis": {
            "anzahl_projekte": len(projekte_set),
            "anzahl_spritzguss_kalkulationen": len(sg),
            "anzahl_baugruppen": len(bg),
            "durchschnitt_endpreis_einzelteil": round(mean(sg_preise), 2) if sg_preise else None,
            "durchschnitt_baugruppenpreis": round(mean(bg_preise), 2) if bg_preise else None,
            "investitionen_gesamt": round(sum(float(r.amount) for r in inv), 2),
            "jahresstueckzahl": jahresstueckzahl,
            "umsatzpotenzial_jahr": round(umsatzpotenzial, 2),
        },
        "recent_calculations": recent,
        "assemblies": assemblies,
        "investments": investments,
        "price_comparison": price_comparison,
        "investment_by_project": [
            {"projekt": k, "betrag": round(v, 2)}
            for k, v in sorted(inv_by_project.items(), key=lambda x: x[1], reverse=True)
        ],
        "revenue_by_project": [
            {"projekt": k, "betrag": round(v, 2)}
            for k, v in sorted(rev_by_project.items(), key=lambda x: x[1], reverse=True)
        ],
        "filter_options": filter_options,
    }

"""Dashboard-Aggregation aus gespeicherten Kalkulationsdaten."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
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
    status: str = "aktiv"


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
    status: str = "entwurf"


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
    supplier: str = ""
    order_date: date | None = None
    delivery_date: date | None = None
    amortization_volume: int | None = None
    cost_per_piece: float | None = None
    created_at: datetime | None = None
    name: str = ""


def parse_json_dict(value: object) -> dict | None:
    """JSONB oder SQLite-TEXT als dict lesen – ohne Schreibzugriff."""
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


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
        preis = ergebnis.get("endpreis_je_stueck")
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


def _sort_key_dt(value: datetime | date | None) -> datetime:
    if value is None:
        return datetime.min.replace(tzinfo=timezone.utc)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)


def _as_date(value: datetime | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    return value


def _in_date_range(
    value: datetime | date | None,
    *,
    date_from: date | None,
    date_to: date | None,
) -> bool:
    if date_from is None and date_to is None:
        return True
    current = _as_date(value)
    if current is None:
        return False
    if date_from is not None and current < date_from:
        return False
    if date_to is not None and current > date_to:
        return False
    return True


def _parse_filter_date(value: date | datetime | str | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _filter_spritzguss(
    rows: list[SpritzgussRecord],
    *,
    project: str | None,
    customer: str | None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    kalkulationsart: str | None = None,
) -> list[SpritzgussRecord]:
    if kalkulationsart and kalkulationsart.casefold() == "baugruppe":
        return []
    result: list[SpritzgussRecord] = []
    for row in rows:
        if status:
            if not _matches(row.status or ("aktiv" if row.aktiv else "inaktiv"), status):
                continue
        elif not row.aktiv:
            continue
        if not _matches(row.projekt, project) or not _matches(row.kunde, customer):
            continue
        if not _in_date_range(row.updated_at, date_from=date_from, date_to=date_to):
            continue
        result.append(row)
    return result


def _filter_baugruppen(
    rows: list[BaugruppeRecord],
    *,
    project: str | None,
    customer: str | None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    kalkulationsart: str | None = None,
) -> list[BaugruppeRecord]:
    if kalkulationsart and kalkulationsart.casefold() == "spritzguss":
        return []
    result: list[BaugruppeRecord] = []
    for row in rows:
        if status:
            if not _matches(row.status, status):
                continue
        elif not row.aktiv:
            continue
        if not _matches(row.projekt, project) or not _matches(row.kunde, customer):
            continue
        if not _in_date_range(row.updated_at, date_from=date_from, date_to=date_to):
            continue
        result.append(row)
    return result


def _filter_investitionen(
    rows: list[InvestitionRecord],
    *,
    project: str | None,
    customer: str | None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[InvestitionRecord]:
    result: list[InvestitionRecord] = []
    for row in rows:
        projekt = row.projekt or row.project_id
        if not _matches(projekt, project):
            continue
        if not _matches(row.kunde, customer):
            continue
        if status and not _matches(row.status, status):
            continue
        if not _in_date_range(row.created_at or row.order_date, date_from=date_from, date_to=date_to):
            continue
        result.append(row)
    return result


COST_STRUCTURE_LABELS = ("Material", "Fertigung", "Werkzeug", "Veredelung", "Gemeinkosten")


def cost_buckets_from_spritzguss(ergebnis: dict | None) -> dict[str, float]:
    """Material / Fertigung / Veredelung / Gemeinkosten aus gespeichertem Spritzguss-Ergebnis."""
    buckets = {label: 0.0 for label in COST_STRUCTURE_LABELS}
    data = parse_json_dict(ergebnis) or (ergebnis if isinstance(ergebnis, dict) else None)
    if not data:
        return buckets
    buckets["Material"] = float(
        data.get("materialkosten_inkl_ausschuss") or data.get("materialkosten") or 0
    )
    buckets["Fertigung"] = float(data.get("maschinenkosten") or 0) + float(
        data.get("fertigungslohn") or 0
    )
    buckets["Veredelung"] = float(data.get("veredelung_gesamt") or 0)
    buckets["Gemeinkosten"] = (
        float(data.get("materialgemeinkosten") or 0)
        + float(data.get("fertigungsgemeinkosten") or 0)
        + float(data.get("vvgk") or 0)
    )
    return buckets


def cost_structure_from_ergebnis(
    ergebnis: dict | None,
    *,
    investitionen_betrag: float = 0.0,
    spritzguss_ergebnisse: list[dict | None] | None = None,
) -> list[dict]:
    material = 0.0
    fertigung = 0.0
    werkzeug = max(float(investitionen_betrag), 0.0)
    veredelung = 0.0
    gemeinkosten = 0.0
    data = parse_json_dict(ergebnis) or (ergebnis if isinstance(ergebnis, dict) else None)
    used_spritzguss = False
    if spritzguss_ergebnisse:
        for sg_ergebnis in spritzguss_ergebnisse:
            part = cost_buckets_from_spritzguss(sg_ergebnis)
            if any(part[label] for label in COST_STRUCTURE_LABELS if label != "Werkzeug"):
                used_spritzguss = True
            material += part["Material"]
            fertigung += part["Fertigung"]
            veredelung += part["Veredelung"]
            gemeinkosten += part["Gemeinkosten"]
    if isinstance(data, dict):
        gemeinkosten += float(data.get("vvgk") or 0) if not used_spritzguss else 0.0
        positions = data.get("positions") or []
        if isinstance(positions, list) and positions and not used_spritzguss:
            for pos in positions:
                if not isinstance(pos, dict):
                    continue
                amount = float(pos.get("zwischensumme") or 0)
                ptype = pos.get("position_type")
                if ptype == "PROCESS":
                    veredelung += amount
                else:
                    material += amount
        elif not used_spritzguss:
            material += float(data.get("einzelteile_gesamt") or 0) + float(
                data.get("kaufteile_gesamt") or 0
            )
            veredelung += float(data.get("veredelung_gesamt") or 0)
    buckets = [
        ("Material", material),
        ("Fertigung", fertigung),
        ("Werkzeug", werkzeug),
        ("Veredelung", veredelung),
        ("Gemeinkosten", gemeinkosten),
    ]
    return [{"label": label, "value": round(value, 2)} for label, value in buckets]


def build_filter_options(
    spritzguss_rows: list[SpritzgussRecord],
    baugruppe_rows: list[BaugruppeRecord],
    investition_rows: list[InvestitionRecord] | None = None,
) -> dict[str, list[str]]:
    projekte: set[str] = set()
    kunden: set[str] = set()
    statusse: set[str] = set()
    for row in spritzguss_rows:
        if not row.aktiv:
            continue
        if row.projekt.strip():
            projekte.add(row.projekt.strip())
        if row.kunde.strip():
            kunden.add(row.kunde.strip())
        statusse.add(row.status or "aktiv")
    for row in baugruppe_rows:
        if not row.aktiv:
            continue
        if row.projekt.strip():
            projekte.add(row.projekt.strip())
        if row.kunde.strip():
            kunden.add(row.kunde.strip())
        if row.status.strip():
            statusse.add(row.status.strip())
    for row in investition_rows or []:
        if row.status.strip():
            statusse.add(row.status.strip())
        if (row.projekt or row.project_id).strip():
            projekte.add((row.projekt or row.project_id).strip())
        if row.kunde.strip():
            kunden.add(row.kunde.strip())
    return {
        "projekte": sorted(projekte, key=str.casefold),
        "kunden": sorted(kunden, key=str.casefold),
        "statusse": sorted(statusse, key=str.casefold),
        "kalkulationsarten": ["Spritzguss", "Baugruppe"],
    }


def build_dashboard_summary(
    spritzguss_rows: list[SpritzgussRecord],
    baugruppe_rows: list[BaugruppeRecord],
    investition_rows: list[InvestitionRecord],
    *,
    project: str | None = None,
    customer: str | None = None,
    status: str | None = None,
    date_from: date | datetime | str | None = None,
    date_to: date | datetime | str | None = None,
    kalkulationsart: str | None = None,
) -> dict:
    parsed_from = _parse_filter_date(date_from)
    parsed_to = _parse_filter_date(date_to)
    filter_options = build_filter_options(spritzguss_rows, baugruppe_rows, investition_rows)

    sg = _filter_spritzguss(
        spritzguss_rows,
        project=project,
        customer=customer,
        status=status,
        date_from=parsed_from,
        date_to=parsed_to,
        kalkulationsart=kalkulationsart,
    )
    bg = _filter_baugruppen(
        baugruppe_rows,
        project=project,
        customer=customer,
        status=status,
        date_from=parsed_from,
        date_to=parsed_to,
        kalkulationsart=kalkulationsart,
    )
    inv = _filter_investitionen(
        investition_rows,
        project=project,
        customer=customer,
        status=status,
        date_from=parsed_from,
        date_to=parsed_to,
    )

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
    recent.sort(key=lambda x: _sort_key_dt(x["updated_at"]), reverse=True)
    recent = recent[:20]

    assemblies = [
        {
            "id": row.id,
            "name": row.name,
            "teilenummer": row.teilenummer,
            "kunde": row.kunde,
            "projekt": row.projekt,
            "status": row.status,
            "preis_je_stueck": preis_aus_baugruppe(row.ergebnis),
            "jahresstueckzahl": row.jahresstueckzahl,
            "jahresumsatz": jahresumsatz_aus_baugruppe(row.ergebnis, row.jahresstueckzahl),
            "letzte_kalkulation": row.updated_at,
            "cost_structure": cost_structure_from_ergebnis(
                row.ergebnis,
                investitionen_betrag=sum(
                    float(i.amount) for i in inv if i.baugruppe_id == row.id
                ),
            ),
        }
        for row in sorted(bg, key=lambda r: _sort_key_dt(r.updated_at), reverse=True)
    ]

    investments = []
    for row in inv:
        einmal = row.payment_type.casefold() == "einmalzahlung"
        investments.append(
            {
                "id": row.id,
                "bezeichnung": row.name or row.description or row.part_name,
                "typ": row.investment_type,
                "betrag": float(row.amount),
                "projekt": row.projekt or row.project_id,
                "kunde": row.kunde,
                "status": row.status,
                "lieferant": row.supplier,
                "bestelldatum": row.order_date,
                "liefertermin": row.delivery_date,
                "amortisationsvolumen": row.amortization_volume,
                "kostenanteil_pro_teil": row.cost_per_piece,
                "created_at": row.created_at,
                "im_stueckpreis": False,
                "hinweis": (
                    "Separat, nicht im Stückpreis enthalten"
                    if einmal
                    else "Separat ausgewiesen"
                ),
            }
        )

    recent_investments = sorted(
        investments,
        key=lambda x: _sort_key_dt(x["created_at"]),
        reverse=True,
    )[:10]

    cost_totals = {label: 0.0 for label in COST_STRUCTURE_LABELS}
    for assembly in assemblies:
        for bucket in assembly["cost_structure"]:
            cost_totals[bucket["label"]] = cost_totals.get(bucket["label"], 0.0) + float(
                bucket["value"]
            )
    cost_structure = [
        {"label": label, "value": round(cost_totals[label], 2)}
        for label in COST_STRUCTURE_LABELS
    ]
    has_data = bool(sg or bg or inv)
    empty_message = (
        None
        if has_data
        else (
            "Keine Daten für die gewählten Filter. "
            "Setzen Sie die Filter zurück oder legen Sie Projekte, Kalkulationen oder Investitionen an."
        )
    )
    all_prices = sg_preise + bg_preise

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
            "durchschnitt_preis_pro_stueck": round(mean(all_prices), 2) if all_prices else None,
            "investitionen_gesamt": round(sum(float(r.amount) for r in inv), 2),
            "jahresstueckzahl": jahresstueckzahl,
            "umsatzpotenzial_jahr": round(umsatzpotenzial, 2),
        },
        "recent_calculations": recent,
        "recent_investments": recent_investments,
        "assemblies": assemblies,
        "investments": investments,
        "price_comparison": price_comparison,
        "cost_structure": cost_structure,
        "investment_by_project": [
            {"projekt": k, "betrag": round(v, 2)}
            for k, v in sorted(inv_by_project.items(), key=lambda x: x[1], reverse=True)
        ],
        "revenue_by_project": [
            {"projekt": k, "betrag": round(v, 2)}
            for k, v in sorted(rev_by_project.items(), key=lambda x: x[1], reverse=True)
        ],
        "filter_options": filter_options,
        "has_data": has_data,
        "empty_message": empty_message,
    }

"""Automatische Losgröße über werksspezifisches Produktionsintervall (keine EOQ/Andler)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from sqlalchemy.orm import Session

from app.models.werk import Werk
from app.services.project_volume_service import average_jahresstueckzahl_for_project

DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE = 30
LosgroesseModus = Literal["automatisch", "manuell"]


class LosgroesseValidationError(ValueError):
    """Ungültige oder unvollständige Eingaben für die Losgrößenberechnung."""


@dataclass(frozen=True)
class LosgroesseBerechnung:
    jahresbedarf: int
    produktionsintervall_arbeitstage: float
    arbeitstage_pro_jahr: float
    raw_vor_ceil: float
    automatische_losgroesse: int


@dataclass(frozen=True)
class LosgroesseKontext:
    modus: LosgroesseModus
    losgroesse_aktiv: int | None
    losgroesse_automatisch: int | None
    losgroesse_manuell: int | None
    jahresbedarf: int | None
    produktionsintervall_arbeitstage: float | None
    arbeitstage_pro_jahr: float | None
    berechnung: LosgroesseBerechnung | None = None
    hinweis: str | None = None


def berechne_automatische_losgroesse(
    jahresbedarf: float | int,
    produktionsintervall_arbeitstage: float | int,
    arbeitstage_pro_jahr: float | int,
) -> LosgroesseBerechnung:
    """ceil(Jahresbedarf × Intervall ÷ Arbeitstage/Jahr), begrenzt auf [1, Jahresbedarf]."""
    if jahresbedarf is None or float(jahresbedarf) <= 0:
        raise LosgroesseValidationError(
            "Durchschnittlicher Jahresbedarf fehlt oder ist nicht positiv – "
            "keine automatische Losgröße berechenbar."
        )
    if produktionsintervall_arbeitstage is None or float(produktionsintervall_arbeitstage) <= 0:
        raise LosgroesseValidationError(
            "Produktionsintervall muss eine positive Zahl Arbeitstage sein."
        )
    if arbeitstage_pro_jahr is None or float(arbeitstage_pro_jahr) <= 0:
        raise LosgroesseValidationError(
            "Arbeitstage pro Jahr am Werk fehlen oder sind nicht positiv – "
            "bitte im Werk-Stammdatenformular pflegen."
        )

    bedarf = float(jahresbedarf)
    intervall = float(produktionsintervall_arbeitstage)
    tage = float(arbeitstage_pro_jahr)
    raw = bedarf * intervall / tage
    auto = int(math.ceil(raw))
    bedarf_int = int(math.ceil(bedarf))
    auto = max(1, min(auto, bedarf_int))

    return LosgroesseBerechnung(
        jahresbedarf=bedarf_int,
        produktionsintervall_arbeitstage=intervall,
        arbeitstage_pro_jahr=tage,
        raw_vor_ceil=raw,
        automatische_losgroesse=auto,
    )


def werk_produktionsintervall(werk: Werk | None) -> float:
    if werk is None:
        return DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE
    val = getattr(werk, "produktionsintervall_arbeitstage", None)
    if val is None or float(val) <= 0:
        return DEFAULT_PRODUKTIONSINTERVALL_ARBEITSTAGE
    return float(val)


def infer_losgroesse_modus(
    modus: str | None,
    *,
    losgroesse_gespeichert: int | None,
    losgroesse_manuell: int | None,
) -> LosgroesseModus:
    if modus in ("automatisch", "manuell"):
        return modus  # type: ignore[return-value]
    if losgroesse_manuell is not None or losgroesse_gespeichert is not None:
        return "manuell"
    return "automatisch"


def resolve_losgroesse(
    db: Session,
    *,
    modus: str | None,
    losgroesse_manuell: int | None,
    losgroesse_gespeichert: int | None,
    project_id: int | None,
    werk_id: int | None,
    setup_aktiv: bool,
) -> LosgroesseKontext:
    """Ermittelt Modus und aktive Losgröße für Setup-Umlage."""
    effective_modus = infer_losgroesse_modus(
        modus,
        losgroesse_gespeichert=losgroesse_gespeichert,
        losgroesse_manuell=losgroesse_manuell,
    )

    werk = db.get(Werk, werk_id) if werk_id else None
    intervall = werk_produktionsintervall(werk)
    arbeitstage = float(werk.arbeitstage_pro_jahr) if werk and werk.arbeitstage_pro_jahr else None

    jahresbedarf: int | None = None
    berechnung: LosgroesseBerechnung | None = None
    auto: int | None = None
    hinweis: str | None = None

    if project_id is not None:
        avg = average_jahresstueckzahl_for_project(db, project_id)
        if avg.has_volumes and avg.jahresstueckzahl is not None:
            jahresbedarf = avg.jahresstueckzahl

    if jahresbedarf is not None and arbeitstage is not None and project_id is not None and werk_id is not None:
        try:
            berechnung = berechne_automatische_losgroesse(
                jahresbedarf, intervall, arbeitstage
            )
            auto = berechnung.automatische_losgroesse
        except LosgroesseValidationError:
            berechnung = None

    if effective_modus == "automatisch":
        if project_id is None or werk_id is None:
            hinweis = (
                "Automatische Losgröße benötigt Projekt und Werk. "
                "Bitte zuweisen oder Losgröße manuell überschreiben."
            )
        elif jahresbedarf is None:
            hinweis = (
                "Für das Projekt sind keine Jahresstückzahlen hinterlegt – "
                "keine automatische Losgröße berechenbar."
            )
        elif arbeitstage is None:
            hinweis = "Arbeitstage pro Jahr am Werk fehlen – bitte im Werk-Stammdatenformular pflegen."
        else:
            assert berechnung is not None
            auto = berechnung.automatische_losgroesse

        aktiv = auto
        if setup_aktiv and aktiv is None:
            raise LosgroesseValidationError(hinweis or "Automatische Losgröße nicht berechenbar.")
        return LosgroesseKontext(
            modus="automatisch",
            losgroesse_aktiv=aktiv,
            losgroesse_automatisch=auto,
            losgroesse_manuell=None,
            jahresbedarf=jahresbedarf,
            produktionsintervall_arbeitstage=intervall,
            arbeitstage_pro_jahr=arbeitstage,
            berechnung=berechnung,
            hinweis=hinweis,
        )

    manuell = losgroesse_manuell if losgroesse_manuell is not None else losgroesse_gespeichert
    if setup_aktiv and (manuell is None or int(manuell) < 1):
        raise LosgroesseValidationError(
            "Manuelle Losgröße muss eine positive ganze Zahl sein, wenn Setup aktiv ist."
        )
    if manuell is not None:
        manuell = int(manuell)

    return LosgroesseKontext(
        modus="manuell",
        losgroesse_aktiv=manuell,
        losgroesse_automatisch=auto,
        losgroesse_manuell=manuell,
        jahresbedarf=jahresbedarf,
        produktionsintervall_arbeitstage=intervall if werk_id else None,
        arbeitstage_pro_jahr=arbeitstage,
        berechnung=berechnung,
        hinweis=hinweis,
    )


def losgroesse_metadata_dict(ctx: LosgroesseKontext) -> dict:
    out: dict = {
        "losgroesse_modus": ctx.modus,
        "losgroesse_aktiv": ctx.losgroesse_aktiv,
        "losgroesse_automatisch": ctx.losgroesse_automatisch,
        "losgroesse_manuell": ctx.losgroesse_manuell,
        "losgroesse_jahresbedarf": ctx.jahresbedarf,
        "produktionsintervall_arbeitstage": ctx.produktionsintervall_arbeitstage,
        "arbeitstage_pro_jahr": ctx.arbeitstage_pro_jahr,
        "losgroesse_hinweis": ctx.hinweis,
    }
    if ctx.berechnung is not None:
        out["losgroesse_raw_vor_ceil"] = ctx.berechnung.raw_vor_ceil
    return out

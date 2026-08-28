"""Ausschussquote: DE-Komma in API-Schemas und unveränderte Prozentpunkt-Logik."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.numbers import parse_percent_points
from app.schemas.spritzguss_kalkulation import SpritzgussCalcRequest
from app.services.spritzguss_kalkulation import berechne_spritzguss, SpritzgussInput


def test_parse_percent_points_comma_and_dot():
    assert parse_percent_points("1,5") == pytest.approx(1.5)
    assert parse_percent_points("1.5") == pytest.approx(1.5)
    assert parse_percent_points(1.5) == pytest.approx(1.5)


def test_parse_percent_points_validation():
    with pytest.raises(ValueError, match="negativ"):
        parse_percent_points("-1")
    with pytest.raises(ValueError, match="100"):
        parse_percent_points("100")
    with pytest.raises(ValueError, match="100"):
        parse_percent_points("100,0")


def test_calc_request_accepts_comma_string():
    req = SpritzgussCalcRequest(
        teilegewicht_netto_g=100,
        schussgewicht_g=100,
        materialpreis_pro_kg=10,
        ausschussquote_pct="1,5",
        zykluszeit_s=36,
        maschinenstundensatz=100,
        kavitaeten=1,
        lohnstundensatz=50,
        fgk_pct=0,
        werkzeugkosten_eur=0,
        werkzeug_abrechnungsart="einmalzahlung",
    )
    assert req.ausschussquote_pct == pytest.approx(1.5)


def test_calc_request_rejects_invalid_string():
    with pytest.raises(ValidationError):
        SpritzgussCalcRequest(
            teilegewicht_netto_g=100,
            schussgewicht_g=100,
            materialpreis_pro_kg=10,
            ausschussquote_pct="1,5,0",
            zykluszeit_s=36,
            maschinenstundensatz=100,
            kavitaeten=1,
            lohnstundensatz=50,
            fgk_pct=0,
            werkzeugkosten_eur=0,
        )


def test_berechnung_verwendet_prozentpunkte_geteilt_100():
    ohne = berechne_spritzguss(
        SpritzgussInput(
            teilegewicht_netto_g=100,
            schussgewicht_g=100,
            materialpreis_pro_kg=10,
            ausschussquote_pct=0,
            zykluszeit_s=36,
            maschinenstundensatz=100,
            kavitaeten=1,
            lohnstundensatz=50,
            fgk_pct=0,
            werkzeugkosten_eur=0,
        )
    )
    mit = berechne_spritzguss(
        SpritzgussInput(
            teilegewicht_netto_g=100,
            schussgewicht_g=100,
            materialpreis_pro_kg=10,
            ausschussquote_pct=1.5,
            zykluszeit_s=36,
            maschinenstundensatz=100,
            kavitaeten=1,
            lohnstundensatz=50,
            fgk_pct=0,
            werkzeugkosten_eur=0,
            werkzeug_abrechnungsart="einmalzahlung",
        )
    )
    assert mit.materialkosten_inkl_ausschuss > ohne.materialkosten_inkl_ausschuss
    # Material inkl. Ausschuss = materialkosten / (1 - quote/100), gerundet auf 2 Stellen
    from decimal import Decimal, ROUND_HALF_UP

    raw = Decimal(str(ohne.materialkosten)) / (Decimal("1") - Decimal("1.5") / Decimal("100"))
    expected = float(raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    assert mit.materialkosten_inkl_ausschuss == pytest.approx(expected)

"""Kaufteil-Preis: DE/EN-Dezimalstrings in API-Schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.baugruppe import KaufteilCreate, KaufteilUpdate


def test_kaufteil_create_accepts_comma_price():
    item = KaufteilCreate(
        artikelnummer="K-1",
        bezeichnung="Clip",
        einheit="Stück",
        preis="0,10",
        nominierung="selbstnominiert",
    )
    assert item.preis == pytest.approx(0.1)


def test_kaufteil_create_accepts_dot_price():
    item = KaufteilCreate(
        artikelnummer="K-1",
        bezeichnung="Clip",
        einheit="Stück",
        preis="0.10",
        nominierung="selbstnominiert",
    )
    assert item.preis == pytest.approx(0.1)


def test_kaufteil_update_rejects_invalid_price():
    with pytest.raises(ValidationError):
        KaufteilUpdate(preis="abc")

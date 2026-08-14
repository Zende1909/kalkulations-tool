"""Tests für Normalisierung von Baugruppen-Zuordnungen (PUT als Dict)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.baugruppen import (
    _normalize_kaufteil_zuordnungen,
    _normalize_spritzguss_zuordnungen,
    _normalize_veredelung_zuordnungen,
    _sync_spritzguss_zuordnungen,
)


def test_spritzguss_zuordnung_als_dict():
    result = _normalize_spritzguss_zuordnungen(
        [{"spritzguss_kalkulation_id": 5, "menge": 2, "reihenfolge": 1}]
    )
    assert result[0].spritzguss_kalkulation_id == 5
    assert result[0].menge == 2


def test_mehrere_spritzguss_zuordnungen_als_dict():
    result = _normalize_spritzguss_zuordnungen(
        [
            {"spritzguss_kalkulation_id": 1, "menge": 1, "reihenfolge": 1},
            {"spritzguss_kalkulation_id": 2, "menge": 3, "reihenfolge": 2},
        ]
    )
    assert len(result) == 2


def test_spritzguss_ungueltige_id_fehlt():
    with pytest.raises(HTTPException) as exc:
        _normalize_spritzguss_zuordnungen([{"menge": 1, "reihenfolge": 1}])
    assert exc.value.status_code == 422


@patch("app.api.v1.baugruppen._normalize_spritzguss_zuordnungen")
def test_sync_put_mit_dict(mock_norm):
    mock_norm.return_value = _normalize_spritzguss_zuordnungen(
        [{"spritzguss_kalkulation_id": 99, "menge": 1, "reihenfolge": 1}]
    )
    db = MagicMock()
    kalk = MagicMock()
    kalk.teilebezeichnung = "Stoßfänger"
    kalk.teilenummer = "SF-001"
    kalk.ergebnis = {"endpreis_je_stueck": 12.5}
    db.get.return_value = kalk
    obj = MagicMock()
    obj.id = 1
    with patch("app.api.v1.baugruppen.select") as mock_select:
        mock_select.return_value.where.return_value = []
        db.scalars.return_value.all.return_value = []
        _sync_spritzguss_zuordnungen(
            db,
            obj,
            [{"spritzguss_kalkulation_id": 99, "menge": 1, "reihenfolge": 1}],
        )
    db.add.assert_called()


def test_kaufteil_zuordnung_mit_preis_override():
    result = _normalize_kaufteil_zuordnungen(
        [{"kaufteil_id": 3, "menge": 2, "reihenfolge": 1, "snapshot_preis": 4.99}]
    )
    assert result[0].snapshot_preis == 4.99


def test_veredelung_alias_felder():
    result = _normalize_veredelung_zuordnungen(
        [{"veredelungsschritt_id": 1, "sequence": 2, "quantity_factor": 1.5}]
    )
    assert result[0].reihenfolge == 2
    assert result[0].mengenfaktor == 1.5

"""Tests für Normalisierung und Sync von Veredelungszuordnungen (PUT-Payload als Dict)."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.spritzguss import (
    _normalize_veredelung_zuordnungen,
    _sync_veredelung_zuordnungen,
)
from app.schemas.spritzguss_veredelung import VeredelungZuordnungInput


def test_normalize_einzelne_zuordnung_als_dict():
    result = _normalize_veredelung_zuordnungen(
        [{"veredelungsschritt_id": 3, "reihenfolge": 1, "mengenfaktor": 1.0, "aktiv": True}]
    )
    assert len(result) == 1
    assert result[0] == VeredelungZuordnungInput(
        veredelungsschritt_id=3,
        reihenfolge=1,
        aktiv=True,
        mengenfaktor=1.0,
    )


def test_normalize_mehrere_zuordnungen_als_dict():
    result = _normalize_veredelung_zuordnungen(
        [
            {"veredelungsschritt_id": 1, "reihenfolge": 2, "mengenfaktor": 1.0},
            {"veredelungsschritt_id": 2, "reihenfolge": 1, "mengenfaktor": 2.5, "aktiv": False},
        ]
    )
    assert [z.veredelungsschritt_id for z in result] == [1, 2]
    assert result[1].mengenfaktor == 2.5
    assert result[1].aktiv is False


def test_normalize_unterstuetzt_pydantic_objekte():
    original = VeredelungZuordnungInput(
        veredelungsschritt_id=5, reihenfolge=1, aktiv=True, mengenfaktor=1.0
    )
    result = _normalize_veredelung_zuordnungen([original])
    assert result[0] is original


def test_normalize_alias_feldnamen():
    result = _normalize_veredelung_zuordnungen(
        [{"veredelungsschritt_id": 4, "sequence": 1, "quantity_factor": 0.5}]
    )
    assert result[0].reihenfolge == 1
    assert result[0].mengenfaktor == 0.5


def test_normalize_fehlende_veredelungsschritt_id():
    with pytest.raises(HTTPException) as exc:
        _normalize_veredelung_zuordnungen([{"reihenfolge": 1}])
    assert exc.value.status_code == 422
    assert "veredelungsschritt_id fehlt" in exc.value.detail


def test_normalize_fehlende_reihenfolge():
    with pytest.raises(HTTPException) as exc:
        _normalize_veredelung_zuordnungen([{"veredelungsschritt_id": 1}])
    assert exc.value.status_code == 422
    assert "reihenfolge fehlt" in exc.value.detail


def test_normalize_doppelte_veredelungsschritt_id():
    with pytest.raises(HTTPException) as exc:
        _normalize_veredelung_zuordnungen(
            [
                {"veredelungsschritt_id": 1, "reihenfolge": 1},
                {"veredelungsschritt_id": 1, "reihenfolge": 2},
            ]
        )
    assert exc.value.status_code == 422
    assert "doppelt zugeordnet" in exc.value.detail


@patch("app.api.v1.spritzguss._load_zuordnungen", return_value=[])
def test_sync_mit_dict_zuordnung(mock_load):
    db = MagicMock()
    schritt = MagicMock()
    schritt.bezeichnung = "Montage"
    schritt.veredelungsart = "Montage"
    schritt.taktzeit_s = 10.0
    schritt.anzahl_mitarbeiter = 1
    schritt.lohnstundensatz = 30.0
    schritt.maschinenstundensatz = 50.0
    schritt.verbrauchskosten_je_stueck = 0.0
    schritt.ausschussquote_pct = 0.0
    schritt.fgk_pct = 0.0
    schritt.reihenfolge = 1
    db.get.return_value = schritt

    obj = MagicMock()
    obj.id = 7

    created = _sync_veredelung_zuordnungen(
        db,
        obj,
        [{"veredelungsschritt_id": 12, "reihenfolge": 1, "mengenfaktor": 1.0}],
    )

    assert len(created) == 1
    assert created[0].veredelungsschritt_id == 12
    assert created[0].reihenfolge == 1
    mock_load.assert_called_once_with(db, 7)


@patch("app.api.v1.spritzguss._load_zuordnungen", return_value=[])
def test_sync_mit_mehreren_dict_zuordnungen(mock_load):
    db = MagicMock()

    def get_schritt(_db, schritt_id):
        schritt = MagicMock()
        schritt.bezeichnung = f"Schritt {schritt_id}"
        schritt.veredelungsart = "Montage"
        schritt.taktzeit_s = 10.0
        schritt.anzahl_mitarbeiter = 1
        schritt.lohnstundensatz = 30.0
        schritt.maschinenstundensatz = 50.0
        schritt.verbrauchskosten_je_stueck = 0.0
        schritt.ausschussquote_pct = 0.0
        schritt.fgk_pct = 0.0
        schritt.reihenfolge = 1
        return schritt

    db.get.side_effect = get_schritt
    obj = MagicMock()
    obj.id = 8

    created = _sync_veredelung_zuordnungen(
        db,
        obj,
        [
            {"veredelungsschritt_id": 1, "reihenfolge": 2, "mengenfaktor": 1.0},
            {"veredelungsschritt_id": 2, "reihenfolge": 1, "mengenfaktor": 2.0},
        ],
    )

    assert len(created) == 2
    assert {row.veredelungsschritt_id for row in created} == {1, 2}


@patch("app.api.v1.spritzguss._load_zuordnungen", return_value=[])
def test_sync_ungueltige_veredelungsschritt_id(mock_load):
    db = MagicMock()
    db.get.return_value = None
    obj = MagicMock()
    obj.id = 9

    with pytest.raises(HTTPException) as exc:
        _sync_veredelung_zuordnungen(
            db,
            obj,
            [{"veredelungsschritt_id": 99999, "reihenfolge": 1}],
        )

    assert exc.value.status_code == 404
    assert "99999" in exc.value.detail

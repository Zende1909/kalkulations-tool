"""Tests für projektbezogene Business-Case-API (Legacy-Mock angepasst)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_nicht_authentifizierter_zugriff():
    response = client.get(
        "/api/v1/business-cases",
        params={"customer_id": 1, "program_id": 10, "linked_project_id": 100},
    )
    assert response.status_code == 401
"""Tests für Teilbild-Validierung in Spritzguss-Kalkulationen."""

from __future__ import annotations

import pytest

from app.services.spritzguss_teilbild import MAX_TEILBILD_BYTES, normalize_teilbild

# 1×1 PNG (rot)
TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def test_normalize_teilbild_accepts_valid_png():
    mime, data = normalize_teilbild("image/png", TINY_PNG_B64)
    assert mime == "image/png"
    assert data == TINY_PNG_B64


def test_normalize_teilbild_accepts_data_url():
    mime, data = normalize_teilbild(None, f"data:image/png;base64,{TINY_PNG_B64}")
    assert mime == "image/png"
    assert data == TINY_PNG_B64


def test_normalize_teilbild_clears_empty():
    assert normalize_teilbild(None, None) == (None, None)
    assert normalize_teilbild("image/png", "") == (None, None)
    assert normalize_teilbild("image/png", "   ") == (None, None)


def test_normalize_teilbild_rejects_invalid_mime():
    with pytest.raises(ValueError, match="MIME-Typ"):
        normalize_teilbild("image/gif", TINY_PNG_B64)


def test_normalize_teilbild_rejects_invalid_base64():
    with pytest.raises(ValueError, match="Base64"):
        normalize_teilbild("image/png", "not-valid-base64!!!")


def test_normalize_teilbild_rejects_oversized_payload():
    import base64

    oversized = base64.b64encode(b"x" * (MAX_TEILBILD_BYTES + 1)).decode("ascii")
    with pytest.raises(ValueError, match="zu gro"):
        normalize_teilbild("image/png", oversized)

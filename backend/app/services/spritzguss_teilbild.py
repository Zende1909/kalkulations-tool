"""Validierung für Teilbilder in Spritzguss-Kalkulationen."""

from __future__ import annotations

import base64
import binascii
import re

ALLOWED_TEILBILD_MIMES = frozenset({"image/jpeg", "image/png", "image/webp"})
MAX_TEILBILD_BYTES = 512_000

_DATA_URL_RE = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)


def normalize_teilbild(
    mime: str | None,
    data: str | None,
) -> tuple[str | None, str | None]:
    """Normalisiert MIME + Base64-Payload; leere Werte entfernen das Bild."""
    if data is None or (isinstance(data, str) and not data.strip()):
        return None, None

    raw = data.strip()
    if raw.startswith("data:"):
        match = _DATA_URL_RE.match(raw)
        if not match:
            raise ValueError("Teilbild: ungültiges Data-URL-Format.")
        mime = match.group(1)
        raw = match.group(2).strip()

    mime_norm = (mime or "").strip().lower()
    if mime_norm not in ALLOWED_TEILBILD_MIMES:
        allowed = ", ".join(sorted(ALLOWED_TEILBILD_MIMES))
        raise ValueError(f"Teilbild: ungültiger MIME-Typ. Erlaubt: {allowed}")

    try:
        decoded = base64.b64decode(raw, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Teilbild: Base64-Daten sind ungültig.") from exc

    if len(decoded) > MAX_TEILBILD_BYTES:
        raise ValueError(
            f"Teilbild zu groß ({len(decoded) // 1024} KB). Maximum: {MAX_TEILBILD_BYTES // 1024} KB."
        )

    return mime_norm, raw

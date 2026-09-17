"""Produkt- und CI-Branding für Exporte und API-Metadaten."""

from __future__ import annotations

from pathlib import Path

PRODUCT_NAME = "ZC PartCalc"
COMPANY_BRAND = "ZENDE Consultant"

# Logo liegt neben den App-Paketen unter backend/app/assets/
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
LOGO_PATH = _ASSETS_DIR / "zende-logo.jpg"


def resolve_logo_path() -> Path | None:
    """Gibt den Logo-Pfad zurück, falls die Datei vorhanden ist."""
    if LOGO_PATH.is_file():
        return LOGO_PATH
    return None

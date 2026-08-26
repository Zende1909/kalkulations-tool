"""Werk: standortbezogene Betriebs- und Kostenparameter für Maschinenstundensatz.

Revision ID: e1a0009_werk_operating_params
Revises: e1a0008_plant_costing
Create Date: 2026-08-26

Fachliche Trennung (Plant Costing / Mappe1):
- Werk: Kapazität (Tage/Schichten/Stunden/OEE), Space-Satz, Kapitalkostensätze,
  Energiepreise, Währung/FX.
- Maschine: Investment, Fläche, Verbräuche, Setup-Zeit/-Mitarbeiteranzahl,
  Schließkraft, Typ – Stundensatz wird aus Maschine+Werk berechnet.

Idempotent: Spalten nur hinzufügen, wenn fehlend. Keine Seeds/DML.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0009_werk_operating_params"
down_revision: Union[str, Sequence[str], None] = "e1a0008_plant_costing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

WERK_OPERATING_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("arbeitstage_pro_jahr", sa.Float()),
    ("schichten_pro_tag", sa.Float()),
    ("stunden_pro_schicht", sa.Float()),
    ("oee", sa.Float()),
    ("space_cost_satz_pro_sqm_jahr", sa.Float()),
    ("abschreibungsdauer_jahre", sa.Float()),
    ("zinssatz", sa.Float()),
    ("versicherungssatz", sa.Float()),
    ("instandhaltungssatz", sa.Float()),
    ("strompreis", sa.Float()),
    ("druckluftpreis", sa.Float()),
    ("kuehlwasserpreis", sa.Float()),
)


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("werke"):
        return
    existing = {c["name"] for c in insp.get_columns("werke")}
    for name, col_type in WERK_OPERATING_COLUMNS:
        if name not in existing:
            op.add_column("werke", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("werke"):
        return
    existing = {c["name"] for c in insp.get_columns("werke")}
    for name, _ in reversed(WERK_OPERATING_COLUMNS):
        if name in existing:
            op.drop_column("werke", name)

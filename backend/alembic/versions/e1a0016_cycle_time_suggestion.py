"""Thermische Materialdaten und Zykluszeitvorschlag (IKET).

Revision ID: e1a0016_cycle_time_suggestion
Revises: e1a0015_injection_machine_sizing
Create Date: 2026-08-31
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0016_cycle_time_suggestion"
down_revision: Union[str, Sequence[str], None] = "e1a0015_injection_machine_sizing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MATERIAL_COLUMNS = [
    sa.Column("materialgruppe", sa.String(length=32), nullable=True),
    sa.Column("schmelzdichte_kg_m3", sa.Float(), nullable=True),
    sa.Column("waermekapazitaet_j_kg_k", sa.Float(), nullable=True),
    sa.Column("waermeleitfaehigkeit_w_m_k", sa.Float(), nullable=True),
    sa.Column("werkzeugtemperatur_c", sa.Float(), nullable=True),
    sa.Column("schmelzetemperatur_c", sa.Float(), nullable=True),
    sa.Column("entformungstemperatur_c", sa.Float(), nullable=True),
]

KALKULATION_COLUMNS = [
    sa.Column("zykluszeit_quelle", sa.String(length=16), nullable=True),
    sa.Column("zykluszeit_wandstaerke_mm", sa.Float(), nullable=True),
    sa.Column("zykluszeit_variante", sa.Integer(), nullable=True),
    sa.Column("zykluszeit_kuehlfaktor", sa.Float(), nullable=True),
    sa.Column("zykluszeit_komponenten", sa.Integer(), nullable=True),
    sa.Column("zykluszeit_nz_werkzeug_schliessen_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_nz_duese_anlegen_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_nz_einspritzen_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_nz_werkzeug_oeffnen_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_nz_auswerfen_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_nz_kernzug_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_nz_ausschrauben_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_nz_einlegen_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_nz_ausblasen_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_temperaturleitfaehigkeit_m2_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_optimale_kuehlzeit_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_kuehlzeit_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_nebenzeiten_gesamt_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_vorschlag_s", sa.Float(), nullable=True),
    sa.Column("zykluszeit_hinweis", sa.String(length=512), nullable=True),
]


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table(table):
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def _drop_column_if_present(table: str, name: str) -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table(table):
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    if name in existing:
        op.drop_column(table, name)


def upgrade() -> None:
    for column in MATERIAL_COLUMNS:
        _add_column_if_missing("materialien", column)
    for column in KALKULATION_COLUMNS:
        _add_column_if_missing("spritzguss_kalkulationen", column)

    # Bestandskalkulationen behalten ihre eingetragene Zykluszeit; sie gilt als manuell.
    bind = op.get_bind()
    insp = inspect(bind)
    if insp.has_table("spritzguss_kalkulationen"):
        op.execute(
            sa.text(
                "UPDATE spritzguss_kalkulationen SET zykluszeit_quelle = 'manuell' "
                "WHERE zykluszeit_quelle IS NULL"
            )
        )


def downgrade() -> None:
    for column in reversed(KALKULATION_COLUMNS):
        _drop_column_if_present("spritzguss_kalkulationen", column.name)
    for column in reversed(MATERIAL_COLUMNS):
        _drop_column_if_present("materialien", column.name)

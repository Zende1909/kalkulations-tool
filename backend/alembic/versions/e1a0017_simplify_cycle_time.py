"""Zykluszeit-Schätzung auf wenige Parameter reduzieren.

Die thermischen Kennwerte werden nicht mehr je Material gepflegt, sondern über
die Materialgruppe aus einer internen Tabelle gezogen. Statt neun einzelner
Nebenzeiten gibt es eine Größenklasse mit einem Summenrichtwert.

Revision ID: e1a0017_simplify_cycle_time
Revises: e1a0016_cycle_time_suggestion
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0017_simplify_cycle_time"
down_revision: Union[str, Sequence[str], None] = "e1a0016_cycle_time_suggestion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEUE_SPALTEN: list[tuple[str, sa.Column]] = [
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_groessenklasse", sa.String(length=16), nullable=True)),
]

# Spalten aus e1a0016, die durch die Vereinfachung entfallen.
ENTFALLENE_SPALTEN: list[tuple[str, sa.Column]] = [
    ("materialien", sa.Column("schmelzdichte_kg_m3", sa.Float(), nullable=True)),
    ("materialien", sa.Column("waermekapazitaet_j_kg_k", sa.Float(), nullable=True)),
    ("materialien", sa.Column("waermeleitfaehigkeit_w_m_k", sa.Float(), nullable=True)),
    ("materialien", sa.Column("werkzeugtemperatur_c", sa.Float(), nullable=True)),
    ("materialien", sa.Column("schmelzetemperatur_c", sa.Float(), nullable=True)),
    ("materialien", sa.Column("entformungstemperatur_c", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_variante", sa.Integer(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_kuehlfaktor", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_komponenten", sa.Integer(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_nz_werkzeug_schliessen_s", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_nz_duese_anlegen_s", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_nz_einspritzen_s", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_nz_werkzeug_oeffnen_s", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_nz_auswerfen_s", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_nz_kernzug_s", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_nz_ausschrauben_s", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_nz_einlegen_s", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_nz_ausblasen_s", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_temperaturleitfaehigkeit_m2_s", sa.Float(), nullable=True)),
    ("spritzguss_kalkulationen", sa.Column("zykluszeit_optimale_kuehlzeit_s", sa.Float(), nullable=True)),
]


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table(table):
        return
    if column.name not in {c["name"] for c in insp.get_columns(table)}:
        op.add_column(table, column)


def _drop_column_if_present(table: str, name: str) -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table(table):
        return
    if name in {c["name"] for c in insp.get_columns(table)}:
        op.drop_column(table, name)


def upgrade() -> None:
    for table, column in NEUE_SPALTEN:
        _add_column_if_missing(table, column)
    for table, column in ENTFALLENE_SPALTEN:
        _drop_column_if_present(table, column.name)


def downgrade() -> None:
    for table, column in reversed(ENTFALLENE_SPALTEN):
        _add_column_if_missing(table, column)
    for table, column in reversed(NEUE_SPALTEN):
        _drop_column_if_present(table, column.name)

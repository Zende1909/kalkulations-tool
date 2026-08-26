"""Plant costing: Land/Werk, Maschinenparameter, Lohnrollen, Setup-Losgröße.

Revision ID: e1a0008_plant_costing
Revises: e1a0007_veredelung_snapshot_yield
Create Date: 2026-08-26

Nur DDL – keine DML/Seeds. Bestehende Kalkulationen unverändert.

Idempotent: verträgt frische DBs und create_all-/Dev-Bootstrap, bei dem
laender/werke/werk_zuschlaege bereits existieren, Spalten an maschinen/
lohnkosten/… aber noch fehlen.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0008_plant_costing"
down_revision: Union[str, Sequence[str], None] = "e1a0007_veredelung_snapshot_yield"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

MASCHINEN_PLANT_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("werk_id", sa.Integer()),
    ("maschinentyp", sa.String(128)),
    ("variante", sa.String(64)),
    ("source_currency", sa.String(8)),
    ("arbeitstage_pro_jahr", sa.Float()),
    ("schichten_pro_tag", sa.Float()),
    ("stunden_pro_schicht", sa.Float()),
    ("oee", sa.Float()),
    ("investment", sa.Float()),
    ("flaeche_sqm", sa.Float()),
    ("space_cost_satz_pro_sqm_jahr", sa.Float()),
    ("abschreibungsdauer_jahre", sa.Float()),
    ("zinssatz", sa.Float()),
    ("versicherungssatz", sa.Float()),
    ("instandhaltungssatz", sa.Float()),
    ("stromverbrauch_kwh_h", sa.Float()),
    ("strompreis", sa.Float()),
    ("druckluftverbrauch_m3_h", sa.Float()),
    ("druckluftpreis", sa.Float()),
    ("kuehlwasserverbrauch_m3_h", sa.Float()),
    ("kuehlwasserpreis", sa.Float()),
    ("setup_zeit_min", sa.Float()),
    ("setup_mitarbeiter", sa.Float()),
    ("jahresstunden", sa.Float()),
    ("space_costs_pro_stunde", sa.Float()),
    ("abschreibung_pro_stunde", sa.Float()),
    ("zinsen_pro_stunde", sa.Float()),
    ("versicherung_pro_stunde", sa.Float()),
    ("instandhaltung_pro_stunde", sa.Float()),
    ("energie_pro_stunde", sa.Float()),
    ("stundensatz_source", sa.Float()),
    ("rate_updated_at", sa.DateTime(timezone=True)),
)


def _inspector():
    return inspect(op.get_bind())


def _has_table(table: str) -> bool:
    return _inspector().has_table(table)


def _column_names(table: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table)}


def _has_index_on(table: str, columns: list[str], *, unique: bool | None = None) -> bool:
    wanted = list(columns)
    for ix in _inspector().get_indexes(table):
        if list(ix.get("column_names") or []) != wanted:
            continue
        if unique is not None and bool(ix.get("unique")) != unique:
            continue
        return True
    return False


def _has_unique_on(table: str, columns: list[str]) -> bool:
    wanted = list(columns)
    for uq in _inspector().get_unique_constraints(table):
        if list(uq.get("column_names") or []) == wanted:
            return True
    return _has_index_on(table, wanted, unique=True)


def _has_fk(
    table: str,
    constrained_columns: list[str],
    referred_table: str,
    referred_columns: list[str] | None = None,
) -> bool:
    wanted_cols = list(constrained_columns)
    wanted_ref = list(referred_columns or ["id"])
    for fk in _inspector().get_foreign_keys(table):
        if list(fk.get("constrained_columns") or []) != wanted_cols:
            continue
        if fk.get("referred_table") != referred_table:
            continue
        if list(fk.get("referred_columns") or []) != wanted_ref:
            continue
        return True
    return False


def _ensure_index(
    name: str,
    table: str,
    columns: list[str],
    *,
    unique: bool = False,
) -> None:
    if unique:
        if _has_unique_on(table, columns):
            return
    elif _has_index_on(table, columns):
        return
    op.create_index(name, table, columns, unique=unique)


def _ensure_fk(
    name: str,
    source_table: str,
    referent_table: str,
    local_cols: list[str],
    remote_cols: list[str],
    *,
    ondelete: str | None = None,
) -> None:
    if _has_fk(source_table, local_cols, referent_table, remote_cols):
        return
    kwargs: dict = {}
    if ondelete:
        kwargs["ondelete"] = ondelete
    op.create_foreign_key(
        name, source_table, referent_table, local_cols, remote_cols, **kwargs
    )


def _ensure_column(
    table: str,
    name: str,
    col_type: sa.types.TypeEngine,
    *,
    nullable: bool = True,
    server_default: str | sa.Text | None = None,
    drop_server_default_after: bool = False,
) -> None:
    if name in _column_names(table):
        return
    col = sa.Column(
        name,
        col_type,
        nullable=nullable,
        server_default=server_default,
    )
    op.add_column(table, col)
    if drop_server_default_after and server_default is not None:
        op.alter_column(table, name, server_default=None)


def _ensure_laender() -> None:
    if not _has_table("laender"):
        op.create_table(
            "laender",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("code", sa.String(length=16), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column(
                "aktiv", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    _ensure_index("ix_laender_code", "laender", ["code"], unique=True)
    _ensure_index("ix_laender_id", "laender", ["id"])


def _ensure_werke() -> None:
    if not _has_table("werke"):
        op.create_table(
            "werke",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "land_id",
                sa.Integer(),
                sa.ForeignKey("laender.id", ondelete="RESTRICT"),
                nullable=False,
            ),
            sa.Column("code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column(
                "currency", sa.String(length=8), nullable=False, server_default="EUR"
            ),
            sa.Column("fx_to_eur", sa.Float(), nullable=False, server_default="1"),
            sa.Column(
                "aktiv", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
    else:
        _ensure_fk(
            "fk_werke_land_id",
            "werke",
            "laender",
            ["land_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    _ensure_index("ix_werke_code", "werke", ["code"], unique=True)
    _ensure_index("ix_werke_land_id", "werke", ["land_id"])
    _ensure_index("ix_werke_id", "werke", ["id"])


def _ensure_werk_zuschlaege() -> None:
    if not _has_table("werk_zuschlaege"):
        op.create_table(
            "werk_zuschlaege",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "werk_id",
                sa.Integer(),
                sa.ForeignKey("werke.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("typ", sa.String(length=64), nullable=False),
            sa.Column("bezeichnung", sa.String(length=255), nullable=False),
            sa.Column("satz_prozent", sa.Float(), nullable=False),
            sa.Column(
                "kostenbasis",
                sa.String(length=64),
                nullable=False,
                server_default="",
            ),
            sa.Column(
                "aktiv", sa.Boolean(), nullable=False, server_default=sa.text("true")
            ),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("werk_id", "typ", name="uq_werk_zuschlag_werk_typ"),
        )
    else:
        _ensure_fk(
            "fk_werk_zuschlaege_werk_id",
            "werk_zuschlaege",
            "werke",
            ["werk_id"],
            ["id"],
            ondelete="CASCADE",
        )
        if not _has_unique_on("werk_zuschlaege", ["werk_id", "typ"]):
            op.create_unique_constraint(
                "uq_werk_zuschlag_werk_typ", "werk_zuschlaege", ["werk_id", "typ"]
            )
    _ensure_index("ix_werk_zuschlaege_werk_id", "werk_zuschlaege", ["werk_id"])
    _ensure_index("ix_werk_zuschlaege_typ", "werk_zuschlaege", ["typ"])


def _ensure_maschinen_plant() -> None:
    for col_name, col_type in MASCHINEN_PLANT_COLUMNS:
        _ensure_column("maschinen", col_name, col_type, nullable=True)
    _ensure_fk(
        "fk_maschinen_werk_id",
        "maschinen",
        "werke",
        ["werk_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _ensure_index("ix_maschinen_werk_id", "maschinen", ["werk_id"])


def _ensure_lohnkosten_plant() -> None:
    _ensure_column("lohnkosten", "werk_id", sa.Integer(), nullable=True)
    # NOT NULL + temporärer Default für bestehende Zeilen, danach Default entfernen
    # (Modell: default nur ORM-seitig, kein persistenter DB-Default).
    _ensure_column(
        "lohnkosten",
        "rolle",
        sa.String(32),
        nullable=False,
        server_default="sonstig",
        drop_server_default_after=True,
    )
    _ensure_column("lohnkosten", "source_currency", sa.String(8), nullable=True)
    _ensure_column("lohnkosten", "source_rate", sa.Float(), nullable=True)
    _ensure_fk(
        "fk_lohnkosten_werk_id",
        "lohnkosten",
        "werke",
        ["werk_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _ensure_index("ix_lohnkosten_werk_id", "lohnkosten", ["werk_id"])


def _ensure_spritzguss_plant() -> None:
    _ensure_column("spritzguss_kalkulationen", "werk_id", sa.Integer(), nullable=True)
    _ensure_column("spritzguss_kalkulationen", "losgroesse", sa.Integer(), nullable=True)
    _ensure_fk(
        "fk_spritzguss_werk_id",
        "spritzguss_kalkulationen",
        "werke",
        ["werk_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _ensure_index(
        "ix_spritzguss_kalkulationen_werk_id", "spritzguss_kalkulationen", ["werk_id"]
    )


def _ensure_baugruppen_plant() -> None:
    _ensure_column("baugruppen", "werk_id", sa.Integer(), nullable=True)
    _ensure_fk(
        "fk_baugruppen_werk_id",
        "baugruppen",
        "werke",
        ["werk_id"],
        ["id"],
        ondelete="SET NULL",
    )
    _ensure_index("ix_baugruppen_werk_id", "baugruppen", ["werk_id"])


def upgrade() -> None:
    _ensure_laender()
    _ensure_werke()
    _ensure_werk_zuschlaege()
    _ensure_maschinen_plant()
    _ensure_lohnkosten_plant()
    _ensure_spritzguss_plant()
    _ensure_baugruppen_plant()


def downgrade() -> None:
    # Unveränderte Downgrade-Strategie der ursprünglichen e1a0008 (nur dieser Revision).
    op.drop_constraint("fk_baugruppen_werk_id", "baugruppen", type_="foreignkey")
    op.drop_index("ix_baugruppen_werk_id", "baugruppen")
    op.drop_column("baugruppen", "werk_id")

    op.drop_constraint("fk_spritzguss_werk_id", "spritzguss_kalkulationen", type_="foreignkey")
    op.drop_index("ix_spritzguss_kalkulationen_werk_id", "spritzguss_kalkulationen")
    op.drop_column("spritzguss_kalkulationen", "losgroesse")
    op.drop_column("spritzguss_kalkulationen", "werk_id")

    op.drop_constraint("fk_lohnkosten_werk_id", "lohnkosten", type_="foreignkey")
    op.drop_index("ix_lohnkosten_werk_id", "lohnkosten")
    op.drop_column("lohnkosten", "source_rate")
    op.drop_column("lohnkosten", "source_currency")
    op.drop_column("lohnkosten", "rolle")
    op.drop_column("lohnkosten", "werk_id")

    op.drop_constraint("fk_maschinen_werk_id", "maschinen", type_="foreignkey")
    op.drop_index("ix_maschinen_werk_id", "maschinen")
    for col, _ in reversed(MASCHINEN_PLANT_COLUMNS):
        op.drop_column("maschinen", col)

    op.drop_table("werk_zuschlaege")
    op.drop_table("werke")
    op.drop_table("laender")

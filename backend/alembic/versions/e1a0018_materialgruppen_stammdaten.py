"""Materialgruppen-Stammdaten mit Seed aus IKET/Richtwerten."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

from app.services.material_thermik import MATERIALGRUPPEN_DEFAULTS

revision: str = "e1a0018_materialgruppen_stammdaten"
down_revision: Union[str, Sequence[str], None] = "e1a0017_simplify_cycle_time"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

materialgruppen = sa.table(
    "materialgruppen",
    sa.column("gruppe", sa.String),
    sa.column("bezeichnung", sa.String),
    sa.column("schmelzdichte_kg_m3", sa.Float),
    sa.column("waermekapazitaet_j_kg_k", sa.Float),
    sa.column("waermeleitfaehigkeit_w_m_k", sa.Float),
    sa.column("werkzeugtemperatur_c", sa.Float),
    sa.column("schmelzetemperatur_c", sa.Float),
    sa.column("entformungstemperatur_c", sa.Float),
    sa.column("quelle", sa.String),
    sa.column("aktiv", sa.Boolean),
    sa.column("created_at", sa.DateTime(timezone=True)),
    sa.column("updated_at", sa.DateTime(timezone=True)),
)


def _seed_rows() -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "gruppe": d.gruppe,
            "bezeichnung": d.bezeichnung,
            "schmelzdichte_kg_m3": d.schmelzdichte_kg_m3,
            "waermekapazitaet_j_kg_k": d.waermekapazitaet_j_kg_k,
            "waermeleitfaehigkeit_w_m_k": d.waermeleitfaehigkeit_w_m_k,
            "werkzeugtemperatur_c": d.werkzeugtemperatur_c,
            "schmelzetemperatur_c": d.schmelzetemperatur_c,
            "entformungstemperatur_c": d.entformungstemperatur_c,
            "quelle": "iket" if d.gruppe == "POM" else "richtwert",
            "aktiv": True,
            "created_at": now,
            "updated_at": now,
        }
        for d in MATERIALGRUPPEN_DEFAULTS.values()
    ]


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)

    if not insp.has_table("materialgruppen"):
        op.create_table(
            "materialgruppen",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("gruppe", sa.String(length=32), nullable=False),
            sa.Column("bezeichnung", sa.String(length=255), nullable=False),
            sa.Column("schmelzdichte_kg_m3", sa.Float(), nullable=False),
            sa.Column("waermekapazitaet_j_kg_k", sa.Float(), nullable=False),
            sa.Column("waermeleitfaehigkeit_w_m_k", sa.Float(), nullable=False),
            sa.Column("werkzeugtemperatur_c", sa.Float(), nullable=False),
            sa.Column("schmelzetemperatur_c", sa.Float(), nullable=False),
            sa.Column("entformungstemperatur_c", sa.Float(), nullable=False),
            sa.Column(
                "quelle",
                sa.String(length=32),
                nullable=False,
                server_default="benutzerdefiniert",
            ),
            sa.Column("aktiv", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_materialgruppen_gruppe", "materialgruppen", ["gruppe"], unique=True)
        op.create_index("ix_materialgruppen_id", "materialgruppen", ["id"], unique=False)

    count = bind.execute(sa.text("SELECT COUNT(*) FROM materialgruppen")).scalar_one()
    if count == 0:
        op.bulk_insert(materialgruppen, _seed_rows())


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("materialgruppen"):
        return
    op.drop_index("ix_materialgruppen_id", table_name="materialgruppen")
    op.drop_index("ix_materialgruppen_gruppe", table_name="materialgruppen")
    op.drop_table("materialgruppen")

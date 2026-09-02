"""Entfernt die Spalte ``quelle`` aus ``materialgruppen``."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0019_drop_materialgruppe_quelle"
down_revision: Union[str, Sequence[str], None] = "e1a0018_materialgruppen_stammdaten"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("materialgruppen"):
        return
    columns = {c["name"] for c in insp.get_columns("materialgruppen")}
    if "quelle" in columns:
        op.drop_column("materialgruppen", "quelle")


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("materialgruppen"):
        return
    columns = {c["name"] for c in insp.get_columns("materialgruppen")}
    if "quelle" not in columns:
        op.add_column(
            "materialgruppen",
            sa.Column(
                "quelle",
                sa.String(length=32),
                nullable=False,
                server_default="benutzerdefiniert",
            ),
        )

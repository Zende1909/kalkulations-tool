"""Prozessaufwand für Zykluszeit-Schätzung."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0021_zykluszeit_prozessaufwand"
down_revision: Union[str, Sequence[str], None] = "e1a0020_spritzguss_teilbild"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("spritzguss_kalkulationen"):
        return
    columns = {c["name"] for c in insp.get_columns("spritzguss_kalkulationen")}
    if "zykluszeit_prozessaufwand" not in columns:
        op.add_column(
            "spritzguss_kalkulationen",
            sa.Column("zykluszeit_prozessaufwand", sa.String(length=16), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("spritzguss_kalkulationen"):
        return
    columns = {c["name"] for c in insp.get_columns("spritzguss_kalkulationen")}
    if "zykluszeit_prozessaufwand" in columns:
        op.drop_column("spritzguss_kalkulationen", "zykluszeit_prozessaufwand")

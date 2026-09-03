"""Entnahmeart für die Nebenzeit der Zykluszeit-Schätzung.

Bestehende Datensätze erhalten ``greifer`` als Default; die gespeicherte
``zykluszeit_s`` (manuell erfasst oder aus dem Vorschlag übernommen) bleibt
unverändert, es wird nichts neu berechnet.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision: str = "e1a0022_zykluszeit_entnahmeart"
down_revision: Union[str, Sequence[str], None] = "e1a0021_zykluszeit_prozessaufwand"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_ENTNAHMEART = "greifer"


def upgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("spritzguss_kalkulationen"):
        return
    columns = {c["name"] for c in insp.get_columns("spritzguss_kalkulationen")}
    if "zykluszeit_entnahmeart" not in columns:
        op.add_column(
            "spritzguss_kalkulationen",
            sa.Column("zykluszeit_entnahmeart", sa.String(length=16), nullable=True),
        )
    op.execute(
        sa.text(
            "UPDATE spritzguss_kalkulationen "
            "SET zykluszeit_entnahmeart = :default_art "
            "WHERE zykluszeit_entnahmeart IS NULL"
        ).bindparams(default_art=DEFAULT_ENTNAHMEART)
    )


def downgrade() -> None:
    bind = op.get_bind()
    insp = inspect(bind)
    if not insp.has_table("spritzguss_kalkulationen"):
        return
    columns = {c["name"] for c in insp.get_columns("spritzguss_kalkulationen")}
    if "zykluszeit_entnahmeart" in columns:
        op.drop_column("spritzguss_kalkulationen", "zykluszeit_entnahmeart")

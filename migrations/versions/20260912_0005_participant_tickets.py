"""Store ticket count per collection participant."""

import sqlalchemy as sa
from alembic import op

revision = "20260912_0005"
down_revision = "20260911_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "collection_participants",
        sa.Column("tickets_count", sa.Integer(), nullable=False, server_default="1"),
    )
    op.alter_column("collection_participants", "tickets_count", server_default=None)


def downgrade() -> None:
    op.drop_column("collection_participants", "tickets_count")

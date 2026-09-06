"""Store Telegram usernames for people.

Revision ID: 20260906_0003
Revises: 20260906_0002
Create Date: 2026-09-06
"""

import sqlalchemy as sa
from alembic import op

revision = "20260906_0003"
down_revision = "20260906_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("people", sa.Column("telegram_username", sa.String(length=32)))
    op.create_index(
        "uq_people_workspace_telegram_username",
        "people",
        ["workspace_id", "telegram_username"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_people_workspace_telegram_username", table_name="people")
    op.drop_column("people", "telegram_username")

"""Allow collections without a target amount.

Revision ID: 20260911_0004
Revises: 20260906_0003
"""

import sqlalchemy as sa
from alembic import op

revision = "20260911_0004"
down_revision = "20260906_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_collections_default_positive", "collections", type_="check")
    op.drop_constraint("ck_participants_target_positive", "collection_participants", type_="check")
    op.alter_column("collections", "default_target_rub", existing_type=sa.Integer(), nullable=True)
    op.alter_column(
        "collection_participants", "target_rub", existing_type=sa.Integer(), nullable=True
    )


def downgrade() -> None:
    op.execute("UPDATE collections SET default_target_rub = 1 WHERE default_target_rub IS NULL")
    op.execute("UPDATE collection_participants SET target_rub = 1 WHERE target_rub IS NULL")
    op.alter_column("collections", "default_target_rub", existing_type=sa.Integer(), nullable=False)
    op.alter_column(
        "collection_participants", "target_rub", existing_type=sa.Integer(), nullable=False
    )
    op.create_check_constraint(
        "ck_collections_default_positive", "collections", "default_target_rub > 0"
    )
    op.create_check_constraint(
        "ck_participants_target_positive", "collection_participants", "target_rub > 0"
    )

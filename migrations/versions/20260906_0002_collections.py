"""Add collections, periods, participants, and payments.

Revision ID: 20260906_0002
Revises: 20260906_0001
Create Date: 2026-09-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260906_0002"
down_revision = "20260906_0001"
branch_labels = None
depends_on = None


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def soft_delete_columns() -> list[sa.Column]:
    return [
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_by_telegram_user_id", sa.BigInteger()),
    ]


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "collections",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("workspace_id", uuid, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("default_target_rub", sa.Integer(), nullable=False),
        sa.Column("created_by_telegram_user_id", sa.BigInteger(), nullable=False),
        *audit_columns(),
        sa.CheckConstraint("kind in ('monthly', 'one_time')", name="ck_collections_kind"),
        sa.CheckConstraint("default_target_rub > 0", name="ck_collections_default_positive"),
    )
    op.create_index("ix_collections_workspace_id", "collections", ["workspace_id"])
    op.create_table(
        "collection_rounds",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("collection_id", uuid, sa.ForeignKey("collections.id"), nullable=False),
        sa.Column("period_key", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        *audit_columns(),
        sa.UniqueConstraint("collection_id", "period_key", name="uq_round_collection_period"),
    )
    op.create_index("ix_collection_rounds_collection_id", "collection_rounds", ["collection_id"])
    op.create_table(
        "collection_participants",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("round_id", uuid, sa.ForeignKey("collection_rounds.id"), nullable=False),
        sa.Column("person_id", uuid, sa.ForeignKey("people.id"), nullable=False),
        sa.Column("target_rub", sa.Integer(), nullable=False),
        *audit_columns(),
        sa.UniqueConstraint("round_id", "person_id", name="uq_round_participant"),
        sa.CheckConstraint("target_rub > 0", name="ck_participants_target_positive"),
    )
    op.create_index("ix_collection_participants_round_id", "collection_participants", ["round_id"])
    op.create_index(
        "ix_collection_participants_person_id", "collection_participants", ["person_id"]
    )
    op.create_table(
        "collection_payments",
        sa.Column("id", uuid, primary_key=True),
        sa.Column(
            "participant_id", uuid, sa.ForeignKey("collection_participants.id"), nullable=False
        ),
        sa.Column("amount_rub", sa.Integer(), nullable=False),
        sa.Column("created_by_telegram_user_id", sa.BigInteger(), nullable=False),
        *soft_delete_columns(),
        *audit_columns(),
        sa.CheckConstraint("amount_rub > 0", name="ck_collection_payments_amount_positive"),
    )
    op.create_index(
        "ix_collection_payments_participant_id", "collection_payments", ["participant_id"]
    )


def downgrade() -> None:
    op.drop_table("collection_payments")
    op.drop_table("collection_participants")
    op.drop_table("collection_rounds")
    op.drop_table("collections")

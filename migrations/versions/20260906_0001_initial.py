"""Initial accounting schema.

Revision ID: 20260906_0001
Revises:
Create Date: 2026-09-06
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260906_0001"
down_revision = None
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
        "workspaces",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        *audit_columns(),
    )
    op.create_table(
        "chats",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("workspace_id", uuid, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("title", sa.String(length=255)),
        *audit_columns(),
    )
    op.create_index("ix_chats_workspace_id", "chats", ["workspace_id"])
    op.create_table(
        "allowed_actors",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("telegram_user_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=255)),
        *audit_columns(),
    )
    op.create_table(
        "people",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("workspace_id", uuid, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("telegram_user_id", sa.BigInteger()),
        *audit_columns(),
        sa.UniqueConstraint("workspace_id", "name", name="uq_people_workspace_name"),
    )
    op.create_index("ix_people_workspace_id", "people", ["workspace_id"])
    op.create_table(
        "debts",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("workspace_id", uuid, sa.ForeignKey("workspaces.id"), nullable=False),
        sa.Column("person_id", uuid, sa.ForeignKey("people.id"), nullable=False),
        sa.Column("amount_rub", sa.Integer(), nullable=False),
        sa.Column("created_by_telegram_user_id", sa.BigInteger(), nullable=False),
        *soft_delete_columns(),
        *audit_columns(),
        sa.CheckConstraint("amount_rub > 0", name="ck_debts_amount_positive"),
    )
    op.create_index("ix_debts_workspace_id", "debts", ["workspace_id"])
    op.create_index("ix_debts_person_id", "debts", ["person_id"])
    op.create_table(
        "debt_repayments",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("debt_id", uuid, sa.ForeignKey("debts.id"), nullable=False),
        sa.Column("amount_rub", sa.Integer(), nullable=False),
        sa.Column("created_by_telegram_user_id", sa.BigInteger(), nullable=False),
        *soft_delete_columns(),
        *audit_columns(),
        sa.CheckConstraint("amount_rub > 0", name="ck_debt_repayments_amount_positive"),
    )
    op.create_index("ix_debt_repayments_debt_id", "debt_repayments", ["debt_id"])


def downgrade() -> None:
    op.drop_table("debt_repayments")
    op.drop_table("debts")
    op.drop_table("people")
    op.drop_table("allowed_actors")
    op.drop_table("chats")
    op.drop_table("workspaces")

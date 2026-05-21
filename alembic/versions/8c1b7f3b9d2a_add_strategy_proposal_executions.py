"""add_strategy_proposal_executions

Revision ID: 8c1b7f3b9d2a
Revises: 25c070e207b5
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8c1b7f3b9d2a"
down_revision: Union[str, Sequence[str], None] = "25c070e207b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "strategy_proposal_executions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("strategy_id", sa.String(), nullable=False),
        sa.Column("strategy_name", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("operation", sa.String(), nullable=False),
        sa.Column("lots", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=True),
        sa.Column("estimated_value_rub", sa.Float(), nullable=True),
        sa.Column("execution_mode", sa.String(), nullable=False),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('blocked', 'confirmed', 'executed', 'expired', 'failed', 'loaded', "
            "'sent_for_confirmation', 'skipped')",
            name="ck_strategy_proposal_executions_status",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_strategy_proposal_executions_created_at"),
        "strategy_proposal_executions",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_strategy_proposal_executions_id"),
        "strategy_proposal_executions",
        ["id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_strategy_proposal_executions_status"),
        "strategy_proposal_executions",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_strategy_proposal_executions_strategy_id"),
        "strategy_proposal_executions",
        ["strategy_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_strategy_proposal_executions_ticker"),
        "strategy_proposal_executions",
        ["ticker"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_strategy_proposal_executions_ticker"), table_name="strategy_proposal_executions")
    op.drop_index(op.f("ix_strategy_proposal_executions_strategy_id"), table_name="strategy_proposal_executions")
    op.drop_index(op.f("ix_strategy_proposal_executions_status"), table_name="strategy_proposal_executions")
    op.drop_index(op.f("ix_strategy_proposal_executions_id"), table_name="strategy_proposal_executions")
    op.drop_index(op.f("ix_strategy_proposal_executions_created_at"), table_name="strategy_proposal_executions")
    op.drop_table("strategy_proposal_executions")

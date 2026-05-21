"""drop_strategy_proposal_executions

Revision ID: c2f0a7e9d4b1
Revises: b4c7e91a2d6f
Create Date: 2026-05-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "c2f0a7e9d4b1"
down_revision: Union[str, Sequence[str], None] = "b4c7e91a2d6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AUTO_STATUSES = (
    "'blocked', 'confirmed', 'deduped', 'executed', 'execution_started', 'expired', "
    "'failed', 'loaded', 'no_action', 'observed', 'policy_blocked', 'previewed', "
    "'sent_for_confirmation', 'skipped'"
)


def _table_exists(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    """Upgrade schema."""
    if _table_exists("strategy_proposal_executions"):
        op.drop_table("strategy_proposal_executions")


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("strategy_proposal_executions"):
        return

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
        sa.Column("strategy_type", sa.String(), nullable=False),
        sa.Column("run_id", sa.String(), nullable=True),
        sa.Column("dedupe_key", sa.String(), nullable=True),
        sa.Column("dedupe_scope", sa.String(), nullable=True),
        sa.Column("effective_max_order_rub", sa.Float(), nullable=True),
        sa.Column("effective_daily_limit_rub", sa.Float(), nullable=True),
        sa.Column("daily_used_before_rub", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            f"status IN ({AUTO_STATUSES})",
            name="ck_strategy_proposal_executions_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "strategy_type",
            "strategy_id",
            "dedupe_key",
            "dedupe_scope",
            name="uq_strategy_proposal_executions_dedupe",
        ),
    )
    op.create_index("ix_strategy_proposal_executions_created_at", "strategy_proposal_executions", ["created_at"])
    op.create_index("ix_strategy_proposal_executions_id", "strategy_proposal_executions", ["id"])
    op.create_index("ix_strategy_proposal_executions_run_id", "strategy_proposal_executions", ["run_id"])
    op.create_index("ix_strategy_proposal_executions_status", "strategy_proposal_executions", ["status"])
    op.create_index("ix_strategy_proposal_executions_strategy_id", "strategy_proposal_executions", ["strategy_id"])
    op.create_index("ix_strategy_proposal_executions_strategy_type", "strategy_proposal_executions", ["strategy_type"])
    op.create_index("ix_strategy_proposal_executions_ticker", "strategy_proposal_executions", ["ticker"])

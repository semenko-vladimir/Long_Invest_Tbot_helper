"""add_strategy_auto_execution_fields

Revision ID: b4c7e91a2d6f
Revises: 9d2a5f31b7c4
Create Date: 2026-05-19 00:00:02.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b4c7e91a2d6f"
down_revision: Union[str, Sequence[str], None] = "9d2a5f31b7c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


AUTO_STATUSES = (
    "'blocked', 'confirmed', 'deduped', 'executed', 'execution_started', 'expired', "
    "'failed', 'loaded', 'no_action', 'observed', 'policy_blocked', 'previewed', "
    "'sent_for_confirmation', 'skipped'"
)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("strategy_proposal_executions") as batch_op:
        batch_op.add_column(sa.Column("run_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("dedupe_key", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("dedupe_scope", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("effective_max_order_rub", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("effective_daily_limit_rub", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("daily_used_before_rub", sa.Float(), nullable=True))
        batch_op.drop_constraint(
            "ck_strategy_proposal_executions_status",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_strategy_proposal_executions_status",
            f"status IN ({AUTO_STATUSES})",
        )
        batch_op.create_index("ix_strategy_proposal_executions_run_id", ["run_id"], unique=False)
        batch_op.create_unique_constraint(
            "uq_strategy_proposal_executions_dedupe",
            ["strategy_type", "strategy_id", "dedupe_key", "dedupe_scope"],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("strategy_proposal_executions") as batch_op:
        batch_op.drop_constraint("uq_strategy_proposal_executions_dedupe", type_="unique")
        batch_op.drop_index("ix_strategy_proposal_executions_run_id")
        batch_op.drop_constraint(
            "ck_strategy_proposal_executions_status",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_strategy_proposal_executions_status",
            "status IN ('blocked', 'confirmed', 'executed', 'expired', 'failed', 'loaded', "
            "'observed', 'sent_for_confirmation', 'skipped')",
        )
        batch_op.drop_column("daily_used_before_rub")
        batch_op.drop_column("effective_daily_limit_rub")
        batch_op.drop_column("effective_max_order_rub")
        batch_op.drop_column("dedupe_scope")
        batch_op.drop_column("dedupe_key")
        batch_op.drop_column("run_id")

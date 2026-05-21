"""add_strategy_types

Revision ID: 9d2a5f31b7c4
Revises: 8c1b7f3b9d2a
Create Date: 2026-05-19 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9d2a5f31b7c4"
down_revision: Union[str, Sequence[str], None] = "8c1b7f3b9d2a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("strategy_proposal_executions") as batch_op:
        batch_op.add_column(
            sa.Column(
                "strategy_type",
                sa.String(),
                server_default="confirmation_required",
                nullable=False,
            )
        )
        batch_op.drop_constraint(
            "ck_strategy_proposal_executions_status",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_strategy_proposal_executions_status",
            "status IN ('blocked', 'confirmed', 'executed', 'expired', 'failed', 'loaded', "
            "'observed', 'sent_for_confirmation', 'skipped')",
        )
        batch_op.create_index(
            "ix_strategy_proposal_executions_strategy_type",
            ["strategy_type"],
            unique=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("strategy_proposal_executions") as batch_op:
        batch_op.drop_index("ix_strategy_proposal_executions_strategy_type")
        batch_op.drop_constraint(
            "ck_strategy_proposal_executions_status",
            type_="check",
        )
        batch_op.create_check_constraint(
            "ck_strategy_proposal_executions_status",
            "status IN ('blocked', 'confirmed', 'executed', 'expired', 'failed', 'loaded', "
            "'sent_for_confirmation', 'skipped')",
        )
        batch_op.drop_column("strategy_type")

"""add_multi_account_foundation

Revision ID: f7a4c2e9b103
Revises: e6a3b7c9d1f2
Create Date: 2026-09-16 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f7a4c2e9b103"
down_revision: Union[str, Sequence[str], None] = "e6a3b7c9d1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "broker_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_key", sa.String(), nullable=False),
        sa.Column("connection_key", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key", "connection_key", name="uq_broker_connections_provider_key"),
    )
    op.create_index("ix_broker_connections_id", "broker_connections", ["id"])
    op.create_index("ix_broker_connections_provider_key", "broker_connections", ["provider_key"])

    op.create_table(
        "investment_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("broker_connection_id", sa.Integer(), nullable=False),
        sa.Column("external_account_id", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("account_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("access_level", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["broker_connection_id"], ["broker_connections.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "broker_connection_id",
            "external_account_id",
            name="uq_investment_accounts_connection_external",
        ),
    )
    op.create_index("ix_investment_accounts_id", "investment_accounts", ["id"])
    op.create_index(
        "ix_investment_accounts_broker_connection_id",
        "investment_accounts",
        ["broker_connection_id"],
    )
    op.create_index("ix_investment_accounts_last_seen_at", "investment_accounts", ["last_seen_at"])

    op.create_table(
        "strategy_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("investment_account_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=True),
        sa.Column("strategy_key", sa.String(), nullable=True),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("settings_json", sa.Text(), nullable=True),
        sa.Column("analysis_profile_key", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["investment_account_id"], ["investment_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_strategy_profiles_id", "strategy_profiles", ["id"])
    op.create_index(
        "ix_strategy_profiles_investment_account_id",
        "strategy_profiles",
        ["investment_account_id"],
        unique=True,
    )

    op.create_table(
        "portfolio_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("investment_account_id", sa.Integer(), nullable=False),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("total_value", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("freshness", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["investment_account_id"], ["investment_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_portfolio_snapshots_id", "portfolio_snapshots", ["id"])
    op.create_index(
        "ix_portfolio_snapshots_investment_account_id",
        "portfolio_snapshots",
        ["investment_account_id"],
    )
    op.create_index("ix_portfolio_snapshots_captured_at", "portfolio_snapshots", ["captured_at"])

    op.create_table(
        "position_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("portfolio_snapshot_id", sa.Integer(), nullable=False),
        sa.Column("investment_account_id", sa.Integer(), nullable=False),
        sa.Column("instrument_uid", sa.String(), nullable=True),
        sa.Column("figi", sa.String(), nullable=True),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("average_price", sa.Float(), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("market_value", sa.Float(), nullable=True),
        sa.Column("expected_yield", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["investment_account_id"], ["investment_accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["portfolio_snapshot_id"], ["portfolio_snapshots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_position_snapshots_id", "position_snapshots", ["id"])
    op.create_index(
        "ix_position_snapshots_portfolio_snapshot_id",
        "position_snapshots",
        ["portfolio_snapshot_id"],
    )
    op.create_index(
        "ix_position_snapshots_investment_account_id",
        "position_snapshots",
        ["investment_account_id"],
    )
    op.create_index("ix_position_snapshots_instrument_uid", "position_snapshots", ["instrument_uid"])
    op.create_index("ix_position_snapshots_figi", "position_snapshots", ["figi"])
    op.create_index("ix_position_snapshots_ticker", "position_snapshots", ["ticker"])


def downgrade() -> None:
    op.drop_table("position_snapshots")
    op.drop_table("portfolio_snapshots")
    op.drop_table("strategy_profiles")
    op.drop_table("investment_accounts")
    op.drop_table("broker_connections")

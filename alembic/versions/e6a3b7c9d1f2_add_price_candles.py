"""add_price_candles

Revision ID: e6a3b7c9d1f2
Revises: c2f0a7e9d4b1
Create Date: 2026-05-29 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "e6a3b7c9d1f2"
down_revision: Union[str, Sequence[str], None] = "c2f0a7e9d4b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(table_name: str) -> bool:
    return inspect(op.get_bind()).has_table(table_name)


def upgrade() -> None:
    if _table_exists("price_candles"):
        return

    op.create_table(
        "price_candles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("figi", sa.String(), nullable=True),
        sa.Column("interval", sa.String(), nullable=False),
        sa.Column("time", sa.DateTime(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False),
        sa.Column("high", sa.Float(), nullable=False),
        sa.Column("low", sa.Float(), nullable=False),
        sa.Column("close", sa.Float(), nullable=False),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=True),
        sa.Column("as_of_date", sa.String(), nullable=True),
        sa.Column("freshness", sa.String(), nullable=True),
        sa.Column("delay_status", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "interval", "time", name="uq_price_candles_ticker_interval_time"),
    )
    op.create_index("ix_price_candles_id", "price_candles", ["id"])
    op.create_index("ix_price_candles_ticker", "price_candles", ["ticker"])
    op.create_index("ix_price_candles_interval", "price_candles", ["interval"])
    op.create_index("ix_price_candles_time", "price_candles", ["time"])


def downgrade() -> None:
    if _table_exists("price_candles"):
        op.drop_table("price_candles")

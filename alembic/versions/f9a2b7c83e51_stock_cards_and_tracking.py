"""Account statistics, shared instrument notes and read-only stock tracking."""

from alembic import op
import sqlalchemy as sa

revision = "f9a2b7c83e51"
down_revision = "e8f1a6b72d40"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("stock_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("instrument_key", sa.String(), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False), sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_stock_notes_user_id", "stock_notes", ["user_id"])
    op.create_index("ix_stock_notes_instrument_key", "stock_notes", ["instrument_key"])
    op.create_table("stock_tracking",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("investment_account_id", sa.Integer(), sa.ForeignKey("investment_accounts.id"), nullable=False),
        sa.Column("instrument_key", sa.String(), nullable=False), sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("interval_minutes", sa.Integer(), nullable=False), sa.Column("chart_range", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False), sa.Column("next_due_at", sa.DateTime(), nullable=False),
        sa.Column("last_sent_at", sa.DateTime()), sa.Column("last_sent_price", sa.Float()),
        sa.Column("last_message_id", sa.Integer()), sa.Column("attempt_at", sa.DateTime()), sa.Column("error_text", sa.String()),
        sa.Column("closure_notice_pending", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("user_id", "investment_account_id", "instrument_key", name="uq_stock_tracking_position"))
    op.create_index("ix_stock_tracking_user_id", "stock_tracking", ["user_id"])
    op.create_table("stock_refresh_state", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_attempt_at", sa.DateTime()), sa.Column("last_success_at", sa.DateTime()),
        sa.Column("quotes_checked_at", sa.DateTime()), sa.Column("quotes_json", sa.Text(), nullable=False),
        sa.Column("index_json", sa.Text(), nullable=False), sa.Column("account_ids_json", sa.Text()), sa.Column("error_text", sa.String()))
    op.create_table("stock_account_refresh",
        sa.Column("investment_account_id", sa.Integer(), sa.ForeignKey("investment_accounts.id"), primary_key=True),
        sa.Column("checked_at", sa.DateTime()), sa.Column("success_at", sa.DateTime()), sa.Column("error_text", sa.String()))
    op.create_table("stock_chart_cache", sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("instrument_key", sa.String(), nullable=False), sa.Column("interval", sa.String(), nullable=False),
        sa.Column("candles_json", sa.Text(), nullable=False), sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("instrument_key", "interval", name="uq_stock_chart_instrument_interval"))


def downgrade():
    for name in ("stock_chart_cache", "stock_account_refresh", "stock_refresh_state", "stock_tracking", "stock_notes"):
        op.drop_table(name)

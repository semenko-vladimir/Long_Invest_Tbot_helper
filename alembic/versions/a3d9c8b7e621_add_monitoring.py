"""Add account-aware monitoring preferences and event history.

Revision ID: a3d9c8b7e621
Revises: f7a4c2e9b103
"""

from alembic import op
import sqlalchemy as sa

revision = "a3d9c8b7e621"
down_revision = "f7a4c2e9b103"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "monitoring_preferences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("alerts_enabled", sa.Boolean()),
        sa.Column("digest_enabled", sa.Boolean()),
        sa.Column("scope", sa.String()),
        sa.Column("threshold_pct", sa.Float()),
        sa.Column("digest_time", sa.String()),
        sa.Column("sources_json", sa.Text()),
    )
    op.create_table(
        "monitoring_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_key", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("ticker", sa.String()),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text()),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("observed_at", sa.DateTime(), nullable=False),
        sa.Column("payload_json", sa.Text()),
        sa.Column("delivered_at", sa.DateTime()),
        sa.UniqueConstraint("event_key", name="uq_monitoring_event_key"),
    )
    op.create_index("ix_monitoring_events_observed_at", "monitoring_events", ["observed_at"])
    op.create_table(
        "monitoring_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("last_digest_at", sa.DateTime()),
    )


def downgrade() -> None:
    op.drop_table("monitoring_runs")
    op.drop_index("ix_monitoring_events_observed_at", table_name="monitoring_events")
    op.drop_table("monitoring_events")
    op.drop_table("monitoring_preferences")

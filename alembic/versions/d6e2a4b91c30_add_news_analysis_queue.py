"""Persist deduplicated news and account-scoped analysis jobs.

Revision ID: d6e2a4b91c30
Revises: a3d9c8b7e621
"""

from alembic import op
import sqlalchemy as sa

revision = "d6e2a4b91c30"
down_revision = "a3d9c8b7e621"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("monitoring_events") as batch:
        batch.add_column(sa.Column("investment_account_id", sa.Integer(), nullable=True))
        batch.create_foreign_key("fk_monitoring_event_account", "investment_accounts",
                                 ["investment_account_id"], ["id"], ondelete="SET NULL")
    op.create_table(
        "news_articles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_key", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("full_text", sa.Text()),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False),
        sa.Column("prefilter_ticker", sa.String()),
        sa.Column("prefilter_name", sa.String()),
        sa.Column("prefilter_reason", sa.String()),
        sa.UniqueConstraint("article_key", name="uq_news_article_key"),
    )
    op.create_table(
        "news_analysis_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("investment_account_id", sa.Integer(), sa.ForeignKey("investment_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analyzer_version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime()),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("result_json", sa.Text()),
        sa.Column("error_text", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("article_id", "investment_account_id", "analyzer_version",
                            name="uq_news_job_article_account_version"),
    )
    op.create_index("ix_news_jobs_status_due", "news_analysis_jobs", ["status", "next_attempt_at"])


def downgrade() -> None:
    op.drop_index("ix_news_jobs_status_due", table_name="news_analysis_jobs")
    op.drop_table("news_analysis_jobs")
    op.drop_table("news_articles")
    with op.batch_alter_table("monitoring_events") as batch:
        batch.drop_constraint("fk_monitoring_event_account", type_="foreignkey")
        batch.drop_column("investment_account_id")

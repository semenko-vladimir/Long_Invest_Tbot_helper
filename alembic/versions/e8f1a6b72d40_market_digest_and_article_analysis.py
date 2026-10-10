"""Hourly media intake, article assessments and durable daily digest delivery."""

from alembic import op
import sqlalchemy as sa

revision = "e8f1a6b72d40"
down_revision = "d6e2a4b91c30"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("news_analysis_jobs", sa.Column("content_hash", sa.String()))
    op.add_column("news_analysis_jobs", sa.Column("ticker_names_json", sa.Text()))
    op.add_column("price_candles", sa.Column("turnover_rub", sa.Float()))
    op.add_column("news_articles", sa.Column("categories_json", sa.Text(), nullable=False, server_default="[]"))
    op.add_column("news_articles", sa.Column("publication_time_known", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("news_articles", sa.Column("last_seen_at", sa.DateTime()))
    op.add_column("news_articles", sa.Column("body_checked_at", sa.DateTime()))
    op.create_table("news_source_states",
        sa.Column("source", sa.String(), primary_key=True),
        sa.Column("last_attempt_at", sa.DateTime()), sa.Column("last_success_at", sa.DateTime()),
        sa.Column("item_count", sa.Integer(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("error_text", sa.String()), sa.Column("coverage_complete", sa.Boolean(), nullable=False))
    op.create_table("article_analysis_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("article_id", sa.Integer(), sa.ForeignKey("news_articles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("analyzer_version", sa.String(), nullable=False), sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False), sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False), sa.Column("started_at", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()), sa.Column("next_attempt_at", sa.DateTime()),
        sa.Column("result_json", sa.Text()), sa.Column("error_text", sa.String()),
        sa.Column("duration_seconds", sa.Float()), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("article_id", "analyzer_version", name="uq_article_analysis_version"))
    op.create_index("ix_article_analysis_jobs_status", "article_analysis_jobs", ["status"])
    op.create_table("analysis_hourly_budgets",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("hour", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False), sa.Column("attempts", sa.Integer(), nullable=False),
        sa.UniqueConstraint("hour", "kind", name="uq_analysis_hour_kind"))
    op.create_table("market_reports",
        sa.Column("report_date", sa.String(), primary_key=True), sa.Column("as_of_date", sa.String()),
        sa.Column("candidates_json", sa.Text(), nullable=False), sa.Column("selected_json", sa.Text()),
        sa.Column("selection_status", sa.String(), nullable=False), sa.Column("coverage_json", sa.Text(), nullable=False),
        sa.Column("prepared_at", sa.DateTime(), nullable=False))
    op.create_table("market_refresh_state",
        sa.Column("id", sa.Integer(), primary_key=True), sa.Column("universe_json", sa.Text(), nullable=False),
        sa.Column("refreshed_at", sa.DateTime()), sa.Column("as_of_date", sa.String()),
        sa.Column("status", sa.String(), nullable=False), sa.Column("errors_json", sa.Text(), nullable=False))
    op.create_table("digest_deliveries",
        sa.Column("report_date", sa.String(), primary_key=True), sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("text_sent_at", sa.DateTime()), sa.Column("album_sent_at", sa.DateTime()),
        sa.Column("text_attempt_at", sa.DateTime()), sa.Column("album_attempt_at", sa.DateTime()),
        sa.Column("text_message_ids_json", sa.Text()), sa.Column("album_message_ids_json", sa.Text()),
        sa.Column("error_text", sa.String()), sa.Column("ambiguous", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))


def downgrade():
    op.drop_column("news_analysis_jobs", "ticker_names_json")
    op.drop_column("news_analysis_jobs", "content_hash")
    for name in ("digest_deliveries", "market_refresh_state", "market_reports", "analysis_hourly_budgets", "article_analysis_jobs", "news_source_states"):
        op.drop_table(name)
    with op.batch_alter_table("news_articles") as batch:
        batch.drop_column("body_checked_at")
        batch.drop_column("last_seen_at")
        batch.drop_column("publication_time_known")
        batch.drop_column("categories_json")
    with op.batch_alter_table("price_candles") as batch:
        batch.drop_column("turnover_rub")

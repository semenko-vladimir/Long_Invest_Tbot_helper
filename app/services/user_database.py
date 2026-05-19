import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.backend.models.database import Base, SessionLocal, engine as legacy_engine
from app.client.config.users import load_runtime_users_config, users_config_is_configured
from app.services.user_context import UserContext, UserContextResolver


ROOT_DIR = Path(__file__).resolve().parents[2]
SessionFactory = Callable[[], Session]

# Strict SQLite identifier allowlist: ASCII letter or underscore, followed by
# letters/digits/underscores. Refuses spaces, quotes, semicolons, dashes — anything
# that could change the meaning of a string-interpolated PRAGMA call.
_SAFE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class UserDatabaseHandle:
    db_path: Path
    engine: Engine
    session_factory: SessionFactory


_DATABASE_HANDLES: dict[str, UserDatabaseHandle] = {}


def resolve_db_path(db_path: str | Path) -> Path:
    path = Path(db_path)
    if path.is_absolute():
        return path
    return ROOT_DIR / path


def run_migrations_for_user(db_path: str) -> None:
    """Запустить alembic upgrade head для конкретной пользовательской БД."""
    from alembic.config import Config
    from alembic import command

    resolved_path = resolve_db_path(db_path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{resolved_path.as_posix()}")
    baseline_revision = _baseline_revision_for_existing_schema(resolved_path)
    if baseline_revision:
        command.stamp(alembic_cfg, baseline_revision)
    command.upgrade(alembic_cfg, "head")


def session_factory_for_user(user_context: UserContext) -> SessionFactory:
    return session_factory_for_path(user_context.db_path)


def session_factory_for_path(db_path: str | Path) -> SessionFactory:
    resolved_path = resolve_db_path(db_path)
    key = str(resolved_path)
    handle = _DATABASE_HANDLES.get(key)
    if handle is None:
        handle = _create_database_handle(resolved_path)
        _DATABASE_HANDLES[key] = handle
    return handle.session_factory


def get_default_session_factory() -> SessionFactory:
    if not users_config_is_configured():
        return SessionLocal
    return session_factory_for_user(UserContextResolver().default_web_user())


def configure_runtime_databases() -> list[Path]:
    if not users_config_is_configured():
        _ensure_models_registered()
        run_migrations_for_user("database.db")
        Base.metadata.create_all(bind=legacy_engine)
        return [resolve_db_path("database.db")]

    configured_paths = []
    for user in UserContextResolver().enabled_users():
        run_migrations_for_user(user.db_path)
        session_factory_for_user(user)
        configured_paths.append(resolve_db_path(user.db_path))
    return configured_paths


def dispose_user_database_registry() -> None:
    for handle in _DATABASE_HANDLES.values():
        handle.engine.dispose()
    _DATABASE_HANDLES.clear()


def _baseline_revision_for_existing_schema(db_path: Path) -> str | None:
    engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
    try:
        with engine.connect() as conn:
            table_names = {
                row[0]
                for row in conn.execute(
                    text(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    )
                )
            }
            if not table_names or "alembic_version" in table_names:
                return None
            if _has_auto_schedule_fields(conn) and _has_strategy_auto_execution_fields(conn):
                return "head"
            if _has_auto_schedule_fields(conn) and _has_typed_strategy_proposal_executions(conn):
                return "9d2a5f31b7c4"
            if _has_auto_schedule_fields(conn) and _has_strategy_proposal_executions(conn):
                return "8c1b7f3b9d2a"
            if _has_auto_schedule_fields(conn):
                return "25c070e207b5"
            return "11b2d5cade18"
    finally:
        engine.dispose()


def _has_auto_schedule_fields(conn) -> bool:
    plan_columns = _table_columns(conn, "investment_plans")
    execution_columns = _table_columns(conn, "investment_plan_executions")
    return {
        "operation",
        "price_limit",
        "pct_threshold",
        "avg_period_days",
        "confirmation_mode",
    }.issubset(plan_columns) and "skipped_reason" in execution_columns


def _has_strategy_proposal_executions(conn) -> bool:
    table_names = {
        row[0]
        for row in conn.execute(
            text(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        )
    }
    return "strategy_proposal_executions" in table_names


def _has_typed_strategy_proposal_executions(conn) -> bool:
    return "strategy_type" in _table_columns(conn, "strategy_proposal_executions")


def _has_strategy_auto_execution_fields(conn) -> bool:
    columns = _table_columns(conn, "strategy_proposal_executions")
    return {
        "strategy_type",
        "run_id",
        "dedupe_key",
        "dedupe_scope",
        "effective_max_order_rub",
        "effective_daily_limit_rub",
        "daily_used_before_rub",
    }.issubset(columns)


def _table_columns(conn, table_name: str) -> set[str]:
    if not isinstance(table_name, str) or not _SAFE_IDENTIFIER_RE.match(table_name):
        raise ValueError(f"Unsafe SQLite identifier: {table_name!r}")
    rows = conn.execute(text(f"PRAGMA table_info({table_name})"))
    return {row[1] for row in rows}


def _create_database_handle(db_path: Path) -> UserDatabaseHandle:
    _ensure_models_registered()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}",
        connect_args={
            "check_same_thread": False,
            "timeout": 10,
        },
        pool_pre_ping=True,
    )
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))
        conn.execute(text("PRAGMA synchronous=NORMAL"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    return UserDatabaseHandle(
        db_path=db_path,
        engine=engine,
        session_factory=sessionmaker(autocommit=False, autoflush=False, bind=engine),
    )


def _ensure_models_registered() -> None:
    import app.backend.models.research  # noqa: F401
    import app.backend.models.trading  # noqa: F401

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
    if _requires_initial_baseline_stamp(resolved_path):
        command.stamp(alembic_cfg, "11b2d5cade18")
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


def _requires_initial_baseline_stamp(db_path: Path) -> bool:
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
        return bool(table_names) and "alembic_version" not in table_names
    finally:
        engine.dispose()


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
    import app.backend.models.config  # noqa: F401
    import app.backend.models.research  # noqa: F401
    import app.backend.models.trading  # noqa: F401

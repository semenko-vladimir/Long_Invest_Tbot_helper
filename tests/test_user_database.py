import shutil
import unittest
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from app.backend.models.database import Base
import app.backend.models.research  # noqa: F401
import app.backend.models.trading  # noqa: F401
from app.backend.models.trading import Instrument, Order
from app.services.user_context import UserContext
from app.services.user_database import (
    _table_columns,
    dispose_user_database_registry,
    resolve_db_path,
    run_migrations_for_user,
    session_factory_for_user,
)


ROOT = Path(__file__).resolve().parents[1]
TEST_DB_DIR = ROOT / ".test-user-dbs"


class UserDatabaseTests(unittest.TestCase):
    def tearDown(self):
        dispose_user_database_registry()
        shutil.rmtree(TEST_DB_DIR, ignore_errors=True)

    def user(self, user_id: str) -> UserContext:
        return UserContext(
            user_id=user_id,
            display_name=user_id,
            telegram_chat_id=1000,
            sandbox_token="sandbox-token",
            token="prod-token",
            broker_fee=0.3,
            db_path=f".test-user-dbs/{user_id}/database.db",
        )

    def test_session_factory_for_user_creates_isolated_sqlite_files(self):
        user_a = self.user("user-a")
        user_b = self.user("user-b")

        session_a = session_factory_for_user(user_a)()
        try:
            session_a.add(Instrument(ticker="SBER", figi="FIGI-SBER"))
            session_a.add(Order(order_id="order-a", ticker="SBER", signal="manual", bm_value=100.0, operation_type="buy"))
            session_a.commit()
        finally:
            session_a.close()

        session_b = session_factory_for_user(user_b)()
        try:
            self.assertEqual(session_b.query(Instrument).count(), 0)
            self.assertEqual(session_b.query(Order).count(), 0)
            session_b.add(Instrument(ticker="GAZP", figi="FIGI-GAZP"))
            session_b.commit()
        finally:
            session_b.close()

        session_a = session_factory_for_user(user_a)()
        try:
            self.assertEqual(session_a.query(Instrument).count(), 1)
            self.assertEqual(session_a.query(Instrument).first().ticker, "SBER")
            self.assertEqual(session_a.query(Order).count(), 1)
        finally:
            session_a.close()

        self.assertTrue(resolve_db_path(user_a.db_path).exists())
        self.assertTrue(resolve_db_path(user_b.db_path).exists())

    def test_session_factory_reuses_same_factory_for_same_user_path(self):
        user = self.user("default")

        first = session_factory_for_user(user)
        second = session_factory_for_user(user)

        self.assertIs(first, second)

    def test_run_migrations_stamps_existing_create_all_database_without_version(self):
        db_path = TEST_DB_DIR / "legacy" / "database.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
        try:
            Base.metadata.create_all(bind=engine)
            with engine.connect() as conn:
                alembic_table = conn.execute(
                    text("SELECT name FROM sqlite_master WHERE type='table' AND name='alembic_version'")
                ).first()
                self.assertIsNone(alembic_table)
        finally:
            engine.dispose()

        run_migrations_for_user(str(db_path))

        engine = create_engine(f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False})
        try:
            with engine.connect() as conn:
                version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                script = ScriptDirectory.from_config(Config("alembic.ini"))
                self.assertEqual(version, script.get_current_head())
        finally:
            engine.dispose()


class TableColumnsIdentifierTests(unittest.TestCase):
    def test_accepts_known_safe_identifier(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        try:
            with engine.connect() as conn:
                conn.execute(text("CREATE TABLE plans (id INTEGER PRIMARY KEY, ticker TEXT)"))
                columns = _table_columns(conn, "plans")
        finally:
            engine.dispose()
        self.assertEqual(columns, {"id", "ticker"})

    def test_rejects_identifier_with_semicolon(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        try:
            with engine.connect() as conn:
                with self.assertRaises(ValueError):
                    _table_columns(conn, "plans; DROP TABLE plans")
        finally:
            engine.dispose()

    def test_rejects_identifier_with_space(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        try:
            with engine.connect() as conn:
                with self.assertRaises(ValueError):
                    _table_columns(conn, "plans tail")
        finally:
            engine.dispose()

    def test_rejects_empty_or_non_string_identifier(self):
        engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
        try:
            with engine.connect() as conn:
                with self.assertRaises(ValueError):
                    _table_columns(conn, "")
                with self.assertRaises(ValueError):
                    _table_columns(conn, None)
        finally:
            engine.dispose()


if __name__ == "__main__":
    unittest.main()

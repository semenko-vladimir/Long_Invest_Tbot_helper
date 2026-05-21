from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.backend.web.context import get_web_services


def get_default_web_db() -> Iterator[Session]:
    db = get_web_services().session_factory()
    try:
        yield db
    finally:
        db.close()

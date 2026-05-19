from collections.abc import Iterator

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.backend.web.context import get_web_services
from app.client.config import legacy_local_write_api_enabled


def get_default_web_db() -> Iterator[Session]:
    db = get_web_services().session_factory()
    try:
        yield db
    finally:
        db.close()


def require_legacy_local_write_api() -> None:
    """Refuse legacy local-write API calls unless ENABLE_LEGACY_LOCAL_WRITE_API=true."""
    if not legacy_local_write_api_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Legacy local-write API is disabled. Set ENABLE_LEGACY_LOCAL_WRITE_API=true "
                "to opt back in. These endpoints do not place broker orders."
            ),
        )

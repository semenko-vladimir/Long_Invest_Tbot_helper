from secrets import compare_digest

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.client.config import get_web_auth_token, web_auth_enabled


AUTH_COOKIE_NAME = "web_auth_token"
PUBLIC_PATHS = {"/api/health"}
PUBLIC_PREFIXES = ("/static/",)


class WebAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not web_auth_enabled() or _is_public_request(request):
            return await call_next(request)

        configured_token = get_web_auth_token()
        if not configured_token:
            return JSONResponse(
                {"detail": "Web authentication is not configured."},
                status_code=503,
            )

        supplied_token = _request_token(request)
        if supplied_token and compare_digest(supplied_token, configured_token):
            return await call_next(request)

        return JSONResponse(
            {"detail": "Authentication required."},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )


def _is_public_request(request: Request) -> bool:
    if request.method == "OPTIONS":
        return True

    path = request.url.path.rstrip("/") or "/"
    return path in PUBLIC_PATHS or path == "/static" or any(
        path.startswith(prefix) for prefix in PUBLIC_PREFIXES
    )


def _request_token(request: Request) -> str | None:
    return _bearer_token(request.headers.get("authorization")) or request.cookies.get(AUTH_COOKIE_NAME)


def _bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None

    parts = header_value.strip().split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    return parts[1]

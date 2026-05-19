from secrets import compare_digest, token_urlsafe
from urllib.parse import urlparse

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware


CSRF_COOKIE_NAME = "web_csrf_token"
CSRF_FORM_FIELD = "csrf_token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
TOKEN_MAX_AGE_SECONDS = 60 * 60 * 12


class WebCsrfCookieMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if _is_web_request(request) and request.method in SAFE_METHODS:
            get_csrf_token(request)

        response = await call_next(request)
        if _is_web_request(request):
            set_csrf_cookie_if_needed(request, response)
        return response


def get_csrf_token(request: Request) -> str:
    token = getattr(request.state, "csrf_token", None)
    if token:
        return token

    token = request.cookies.get(CSRF_COOKIE_NAME)
    if token:
        request.state.csrf_token = token
        return token

    token = token_urlsafe(32)
    request.state.csrf_token = token
    request.state.csrf_cookie_needs_set = True
    return token


def validate_csrf_form(request: Request, form: dict) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
    form_token = form.get(CSRF_FORM_FIELD)

    if not cookie_token or not form_token or not compare_digest(cookie_token, form_token):
        raise HTTPException(status_code=403, detail="Invalid CSRF token.")

    _validate_same_origin_headers(request)


def set_csrf_cookie_if_needed(request: Request, response) -> None:
    if not getattr(request.state, "csrf_cookie_needs_set", False):
        return

    token = get_csrf_token(request)
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        max_age=TOKEN_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_is_https(request),
    )


def _is_https(request: Request) -> bool:
    scheme = (request.url.scheme or "").lower()
    if scheme == "https":
        return True
    forwarded = request.headers.get("x-forwarded-proto", "")
    return forwarded.split(",", 1)[0].strip().lower() == "https"


def _validate_same_origin_headers(request: Request) -> None:
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")

    if origin and not _same_origin(origin, request):
        raise HTTPException(status_code=403, detail="Invalid request origin.")

    if not origin and referer and not _same_origin(referer, request):
        raise HTTPException(status_code=403, detail="Invalid request referer.")


def _same_origin(value: str, request: Request) -> bool:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return False

    return parsed.scheme == request.url.scheme and parsed.netloc == request.url.netloc


def _is_web_request(request: Request) -> bool:
    path = request.url.path
    return not path.startswith("/api") and not path.startswith("/static")

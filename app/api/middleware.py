"""Rate limiting and security headers for the public, read-only API."""

import threading
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

WINDOW_S = 60.0
RATE_LIMITED_PREFIX = "/v1/"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Fixed-window limit per instance on /v1/*.

    The API is public and anonymous, and Cloud Run runs at most one instance, so an
    instance-wide limit is a hard ceiling on total traffic. Combined with the service
    cache, Firestore reads stay bounded no matter what clients do. A per-client limit
    would need a trusted client IP, which needs a load balancer in front.
    """

    def __init__(self, app: ASGIApp, limit_per_minute: int) -> None:
        super().__init__(app)
        self._limit = limit_per_minute
        self._window_start = time.monotonic()
        self._count = 0
        self._lock = threading.Lock()

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.url.path.startswith(RATE_LIMITED_PREFIX) and not self._allow():
            return JSONResponse(
                {"success": False, "data": None, "error": "rate limit exceeded", "meta": None},
                status_code=429,
                headers={"Retry-After": str(int(WINDOW_S))},
            )
        return await call_next(request)

    def _allow(self) -> bool:
        now = time.monotonic()
        with self._lock:
            if now - self._window_start >= WINDOW_S:
                self._window_start, self._count = now, 0
            self._count += 1
            return self._count <= self._limit


# Everything the dashboard needs comes from this origin (Chart.js is vendored), so the
# policy can be strict: no inline scripts or styles, no third-party hosts, no framing.
STRICT_CSP = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    )
)
# FastAPI's Swagger/ReDoc pages load their UI from a CDN with inline scripts; they get
# the other headers but not the strict CSP.
DOCS_PATHS = ("/docs", "/redoc")
VENDOR_PREFIX = "/vendor/"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        path = request.url.path
        headers = response.headers
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["Referrer-Policy"] = "no-referrer"
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if not path.startswith(DOCS_PATHS):
            headers["Content-Security-Policy"] = STRICT_CSP
        if response.status_code == 200:
            headers["Cache-Control"] = _cache_control(path, headers.get("content-type", ""))
        return response


def _cache_control(path: str, content_type: str) -> str:
    if path.startswith(RATE_LIMITED_PREFIX):
        return "public, max-age=60"
    if path.startswith(VENDOR_PREFIX):
        return "public, max-age=31536000, immutable"  # versioned folder names
    # Page, app.js, styles.css: revalidate (cheap 304 via ETag) so a deploy never mixes
    # a new page with stale scripts.
    return "no-cache"

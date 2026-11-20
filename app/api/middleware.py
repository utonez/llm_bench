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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith(RATE_LIMITED_PREFIX) and response.status_code == 200:
            response.headers["Cache-Control"] = "public, max-age=60"
        return response

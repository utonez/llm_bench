"""FastAPI app factory for the benchmark query API.

Run locally:  uvicorn app.api.main:app --reload
Cloud Run:    uvicorn app.api.main:app --host 0.0.0.0 --port $PORT
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dependencies import get_settings
from app.api.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.api.routes import health_router, v1_router
from app.config import Settings

logger = logging.getLogger("app.api")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="llm-bench API",
        version="0.1.0",
        description="Read-only API over scheduled LLM benchmarks: reliability, latency, "
        "accuracy and NT$ cost per model.",
    )

    # Order: the last added runs first. CORS must wrap everything so even 429s carry it.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RateLimitMiddleware, limit_per_minute=settings.api_rate_limit_per_minute)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,  # explicit list, never "*"
        allow_credentials=False,  # no cookies or auth: the API is public and read-only
        allow_methods=["GET"],
        allow_headers=[],
    )

    app.include_router(health_router)
    app.include_router(v1_router)
    _register_error_handlers(app)

    # Dashboard: same origin as the API, so no CORS is needed for it. Mounted last so
    # API routes win. StaticFiles resolves paths inside this directory only.
    if settings.frontend_dir.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="dashboard")
    return app


def _error(status: int, message: str) -> JSONResponse:
    body = {"success": False, "data": None, "error": message, "meta": None}
    return JSONResponse(body, status_code=status)


def _register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(p) for p in e["loc"][1:]) for e in exc.errors()})
        return _error(422, f"invalid parameter(s): {', '.join(fields)}")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _error(exc.status_code, str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Full detail goes to the server log only; clients get a generic message.
        logger.exception("unhandled error on %s", request.url.path)
        return _error(500, "internal error")


app = create_app()

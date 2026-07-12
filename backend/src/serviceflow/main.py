"""App factory. API error contract per docs/09_API_SPECIFICATION.md par.1."""

import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from serviceflow import __version__
from serviceflow.assets.router import router as assets_router
from serviceflow.config import Settings, get_settings
from serviceflow.customers.router import router as customers_router
from serviceflow.identity.router import router as auth_router
from serviceflow.logging_setup import setup_logging
from serviceflow.platform.health import router as health_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="ServiceFlow",
        version=__version__,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url=None,
    )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "code": "validation_error",
                "message_key": "errors.validation",
                "params": {},
                "field_errors": [
                    {"loc": list(map(str, e["loc"])), "type": e["type"]} for e in exc.errors()
                ],
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error path=%s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "message_key": "errors.internal", "params": {}},
        )

    app.include_router(health_router, prefix="/api/v1/platform", tags=["platform"])
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(customers_router, prefix="/api/v1/customers", tags=["customers"])
    app.include_router(assets_router, prefix="/api/v1", tags=["assets"])
    return app


app = create_app()

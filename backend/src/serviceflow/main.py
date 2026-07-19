"""App factory. API error contract per docs/09_API_SPECIFICATION.md par.1."""

import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

import serviceflow.timeline.service  # noqa: F401 — registers the timeline subscriber
from business_os.identity.router import router as auth_router
from business_os.identity.router import users_router
from business_os.platform.health import router as health_router
from professional_services.actions.router import router as ps_actions_router
from professional_services.assignments.router import router as ps_assignments_router
from professional_services.clients.router import router as ps_clients_router
from serviceflow import __version__
from serviceflow.assets.router import router as assets_router
from serviceflow.attachments.router import router as attachments_router
from serviceflow.commercial.router import router as commercial_router
from serviceflow.config import Settings, get_settings
from serviceflow.contacts.router import router as contacts_router
from serviceflow.customers.router import router as customers_router
from serviceflow.dashboard.router import router as dashboard_router
from serviceflow.logging_setup import setup_logging
from serviceflow.search.router import router as search_router
from serviceflow.service_orders.router import router as orders_router
from serviceflow.tasks.router import router as tasks_router

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
    app.include_router(orders_router, prefix="/api/v1", tags=["orders"])
    app.include_router(commercial_router, prefix="/api/v1", tags=["commercial"])
    app.include_router(tasks_router, prefix="/api/v1", tags=["tasks"])
    app.include_router(attachments_router, prefix="/api/v1", tags=["attachments"])
    app.include_router(contacts_router, prefix="/api/v1", tags=["contacts"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
    app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])
    app.include_router(search_router, prefix="/api/v1", tags=["search"])
    app.include_router(ps_clients_router, prefix="/api/v1/ps", tags=["ps-clients"])
    app.include_router(ps_assignments_router, prefix="/api/v1/ps", tags=["ps-assignments"])
    app.include_router(ps_actions_router, prefix="/api/v1/ps", tags=["ps-actions"])
    return app


app = create_app()

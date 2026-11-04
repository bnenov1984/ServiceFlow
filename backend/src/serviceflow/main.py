"""App factory. API error contract per docs/09_API_SPECIFICATION.md par.1."""

import logging
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import serviceflow.timeline.service  # noqa: F401 — registers the timeline subscriber
from business_os.identity.router import company_router, users_router
from business_os.identity.router import router as auth_router
from business_os.platform.health import router as health_router
from business_os.platform_admin.router import router as platform_admin_router
from business_os.shared_kernel import correlation
from professional_services.actions.router import router as ps_actions_router
from professional_services.assignments.router import router as ps_assignments_router
from professional_services.catalog.router import router as ps_catalog_router
from professional_services.clients.router import router as ps_clients_router
from serviceflow import __version__
from serviceflow.assets.router import router as assets_router
from serviceflow.attachments.router import router as attachments_router
from serviceflow.commercial.contracts import get_payment_summary
from serviceflow.commercial.router import router as commercial_router
from serviceflow.config import Settings, get_settings
from serviceflow.contacts.router import router as contacts_router
from serviceflow.customers.router import router as customers_router
from serviceflow.dashboard.router import router as dashboard_router
from serviceflow.logging_setup import setup_logging
from serviceflow.search.router import router as search_router
from serviceflow.service_orders.contracts import register_payment_summary_provider
from serviceflow.service_orders.router import router as orders_router

logger = logging.getLogger(__name__)

# Composition-root wiring (docs/business-os/04 rule R4): service_orders owns
# the PaymentSummaryProvider port and never imports commercial; commercial
# implements it and never imports service_orders' router/service directly.
# Only this module — allowed to import everything — connects the two.
register_payment_summary_provider(get_payment_summary)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="ServiceFlow",
        version=__version__,
        docs_url="/api/docs" if settings.debug else None,
        redoc_url=None,
    )

    # Only relevant for a separately-hosted frontend (e.g. Render): local dev
    # talks to the backend through Vite's own proxy, which is same-origin
    # from the browser's perspective, so no CORS headers are needed or added
    # there. `allow_origins` is deliberately never "*" — that combination
    # with `allow_credentials=True` is rejected by browsers outright, and
    # would defeat cookie-based auth's own origin check regardless. Added
    # before any other middleware so it wraps the whole stack (FastAPI's
    # add_middleware prepends internally, so the first call here ends up
    # outermost) — CORS headers must be present on preflight (OPTIONS) and
    # on error responses alike, not only on the success path.
    cors_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
            allow_headers=["Content-Type", "X-CSRF-Token"],
        )

    @app.middleware("http")
    async def request_id_middleware(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Every request gets a freshly server-generated correlation id, bound
        for the lifetime of the request so logs and platform audit rows written
        during it can be tied together (business_os.shared_kernel.correlation).

        A previously incoming `X-Request-ID` is never adopted: this project has
        no validated convention for trusting one (no length/charset check ever
        existed), and a client-supplied value is not guaranteed unique or safe
        to log/persist regardless. If a genuine cross-service tracing need
        arises later, add a validated accept-if-well-formed path deliberately —
        do not resurrect the old blind pass-through.
        """
        request_id = correlation.new_id()
        token = correlation.bind(request_id)
        try:
            response = await call_next(request)
        finally:
            correlation.reset(token)
        response.headers[correlation.REQUEST_ID_HEADER] = request_id
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
    # Vendor Control Plane (ADR-BOS-009): a structurally separate namespace whose
    # every route is guarded by require_platform_admin — no tenant session can
    # satisfy it, and nothing under it takes a TenantDep.
    app.include_router(platform_admin_router, prefix="/api/v1/platform-admin",
                       tags=["platform-admin"])
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(customers_router, prefix="/api/v1/customers", tags=["customers"])
    app.include_router(assets_router, prefix="/api/v1", tags=["assets"])
    app.include_router(orders_router, prefix="/api/v1", tags=["orders"])
    app.include_router(commercial_router, prefix="/api/v1", tags=["commercial"])
    # order-workflow-revamp WP-H (Q17/Q17b): tasks removed entirely from the
    # product (order checklist, dashboard widgets, company-level tasks) —
    # unmounted rather than deleted; `serviceflow.tasks`'s table/model stay
    # for a later, separate drop-table migration.
    app.include_router(attachments_router, prefix="/api/v1", tags=["attachments"])
    app.include_router(contacts_router, prefix="/api/v1", tags=["contacts"])
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
    app.include_router(company_router, prefix="/api/v1/company", tags=["company"])
    app.include_router(dashboard_router, prefix="/api/v1", tags=["dashboard"])
    app.include_router(search_router, prefix="/api/v1", tags=["search"])
    app.include_router(ps_clients_router, prefix="/api/v1/ps", tags=["ps-clients"])
    app.include_router(ps_catalog_router, prefix="/api/v1/ps", tags=["ps-catalog"])
    app.include_router(ps_assignments_router, prefix="/api/v1/ps", tags=["ps-assignments"])
    app.include_router(ps_actions_router, prefix="/api/v1/ps", tags=["ps-actions"])
    return app


app = create_app()

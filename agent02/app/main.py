from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from app.agent.planner import HybridPlanner
from app.api import router
from app.api_v2 import router as router_v2
from app.config import Settings, get_settings
from app.database import Database
from app.logging_config import configure_logging, get_logger
from app.observability import metrics
from app.service import InvalidTaskStateError, TaskAccessError, TaskNotFoundError
from app.tools import build_tool_registry

logger = get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    database: Database | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.validate_runtime()
    configure_logging(resolved_settings.log_level)
    resolved_database = database or Database(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if resolved_settings.auto_create_schema:
            resolved_database.create_all()
        yield

    app = FastAPI(
        title="Enterprise AI Agent Workflow Platform",
        version="0.2.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.database = resolved_database
    app.state.registry = build_tool_registry(resolved_settings)
    app.state.planner = HybridPlanner(resolved_settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
    )

    @app.get("/live", tags=["operations"])
    def live(request: Request) -> dict[str, str]:
        return {
            "status": "alive",
            "request_id": request.state.request_id,
        }

    @app.get("/ready", tags=["operations"])
    def ready(request: Request):
        try:
            resolved_database.check_connection()
        except Exception:
            logger.exception(
                "readiness check failed",
                extra={
                    "event": "readiness_failed",
                    "request_id": request.state.request_id,
                },
            )
            return JSONResponse(
                status_code=503,
                content={
                    "status": "not_ready",
                    "request_id": request.state.request_id,
                    "database": "unavailable",
                },
            )
        return {
            "status": "ready",
            "request_id": request.state.request_id,
            "database": "ok",
        }

    @app.get("/metrics", tags=["operations"], include_in_schema=False)
    def prometheus_metrics() -> PlainTextResponse:
        if not resolved_settings.prometheus_enabled:
            return PlainTextResponse("metrics disabled\n", status_code=404)
        return PlainTextResponse(
            metrics.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        started = perf_counter()
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "unhandled request failure",
                extra={
                    "event": "http_error",
                    "request_id": request_id,
                    "route": request.url.path,
                },
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "error": "internal_server_error",
                    "message": "Internal server error",
                    "request_id": request_id,
                },
            )
        response.headers["X-Request-ID"] = request_id
        total_latency_ms = (perf_counter() - started) * 1000
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        if resolved_settings.prometheus_enabled:
            metrics.observe_http(
                request.method,
                route_path,
                response.status_code,
                total_latency_ms,
            )
        logger.info(
            "request completed",
            extra={
                "event": "http_request",
                "request_id": request_id,
                "route": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "total_latency_ms": round(total_latency_ms, 3),
            },
        )
        return response

    @app.exception_handler(TaskNotFoundError)
    async def task_not_found(request: Request, exc: TaskNotFoundError):
        return JSONResponse(
            status_code=404,
            content={
                "error": "task_not_found",
                "message": "Task was not found",
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(TaskAccessError)
    async def task_access_denied(request: Request, exc: TaskAccessError):
        return JSONResponse(
            status_code=403,
            content={
                "error": "task_access_denied",
                "message": "Task belongs to another user",
                "request_id": request.state.request_id,
            },
        )

    @app.exception_handler(InvalidTaskStateError)
    async def invalid_task_state(request: Request, exc: InvalidTaskStateError):
        return JSONResponse(
            status_code=409,
            content={
                "error": "invalid_task_state",
                "message": str(exc),
                "request_id": request.state.request_id,
            },
        )

    if resolved_settings.app_env in {"development", "test"}:
        app.include_router(router)
    else:

        @app.get("/api/v1/health", tags=["operations"])
        def legacy_health(request: Request) -> dict[str, str]:
            resolved_database.check_connection()
            return {
                "status": "ok",
                "request_id": request.state.request_id,
                "database": "ok",
            }

    app.include_router(router_v2)
    web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run("app.main:app", host="0.0.0.0", port=settings.api_port, reload=False)


if __name__ == "__main__":
    run()

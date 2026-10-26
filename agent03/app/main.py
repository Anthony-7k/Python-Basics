from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from app.api import router
from app.config import Settings, get_settings
from app.database import Database
from app.logging_config import configure_logging
from app.observability import render_metrics, track_request
from app.providers import build_providers
from app.repositories import NotFound
from app.services.errors import ServiceError

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, database: Database | None = None) -> FastAPI:
    resolved = settings or get_settings()
    resolved.validate_runtime()
    configure_logging(resolved.log_level)
    db = database or Database(resolved.database_url)
    providers = build_providers(resolved)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if resolved.auto_create_schema:
            db.create_all()
        db.seed_demo(resolved)
        yield

    app = FastAPI(title="DocFlow AI", version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved
    app.state.database = db
    app.state.providers = providers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved.allowed_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "Last-Event-ID", "X-Trace-ID"],
        expose_headers=["X-Trace-ID"],
    )

    @app.middleware("http")
    async def trace_context(request: Request, call_next):
        started = perf_counter()
        trace_id = request.headers.get("X-Trace-ID") or str(uuid4())
        request.state.trace_id = trace_id
        try:
            response = await call_next(request)
        except Exception:
            logger.exception("unhandled request failure", extra={"event": "http.error", "trace_id": trace_id})
            response = JSONResponse(
                status_code=500,
                content={"error": "internal_server_error", "message": "Internal server error", "trace_id": trace_id},
            )
        response.headers["X-Trace-ID"] = trace_id
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        elapsed = perf_counter() - started
        if resolved.metrics_enabled:
            track_request(request.method, route_path, response.status_code, elapsed)
        logger.info(
            "request completed",
            extra={
                "event": "http.request",
                "trace_id": trace_id,
                "method": request.method,
                "route": request.url.path,
                "status_code": response.status_code,
                "latency_ms": round(elapsed * 1000, 3),
            },
        )
        return response

    @app.exception_handler(NotFound)
    async def not_found(request: Request, exc: NotFound):
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "message": "resource not found", "trace_id": request.state.trace_id},
        )

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.code, "message": str(exc), "trace_id": request.state.trace_id},
        )

    @app.get("/health/live", tags=["operations"])
    def live():
        return {"status": "alive"}

    @app.get("/health/ready", tags=["operations"])
    def ready():
        try:
            db.check_connection()
        except Exception:
            return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})
        try:
            db.check_schema()
        except Exception:
            return JSONResponse(status_code=503, content={
                "status": "not_ready", "database": "schema_outdated",
                "message": "Run database migrations before processing documents",
            })
        return {"status": "ready", "database": "ok"}

    @app.get("/metrics", include_in_schema=False)
    def metrics():
        if not resolved.metrics_enabled:
            return Response(status_code=404)
        body, content_type = render_metrics()
        return Response(body, media_type=content_type)

    app.include_router(router)
    web_dist = Path(__file__).resolve().parent.parent / "web" / "dist"
    if web_dist.is_dir():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return app


app = create_app()


def run() -> None:
    uvicorn.run("app.main:app", host="0.0.0.0", port=8003, reload=False)


if __name__ == "__main__":
    run()


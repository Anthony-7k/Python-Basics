import uuid
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.chat import router as chat_router
from app.api.routes.agent import router as agent_router
from app.api.routes.conversations import (
    router as conversations_router,
)
from app.api.routes.documents import (
    router as documents_router,
)
from app.api.routes.health import router as health_router
from app.api.routes.knowledge_bases import (
    router as knowledge_bases_router,
)
from app.core.exceptions import (
    ConversationKnowledgeBaseMismatchError,
    ConversationNotFoundError,
    DocumentReindexConflictError,
    KnowledgeBaseNotFoundError,
    RateLimitExceededError,
    UpstreamServiceError,
    UpstreamTimeoutError,
)
from app.core.logging_config import (
    get_logger,
    setup_logging,
)


setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title="Enterprise Knowledge Agent",
    version="1.0.0",
)


@app.middleware("http")
async def add_request_id(request, call_next):
    started_at = perf_counter()
    request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    response = await call_next(request)

    response.headers["X-Request-ID"] = request_id

    logger.info(
        "request completed",
        extra={
            "event": "http_request",
            "request_id": request_id,
            "route": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "latency_ms": round(
                (perf_counter() - started_at)
                * 1000,
                2,
            ),
            "actor_id": getattr(
                request.state,
                "actor_id",
                None,
            ),
        },
    )

    return response


@app.exception_handler(RateLimitExceededError)
async def rate_limit_handler(
    request: Request,
    exc: RateLimitExceededError,
):
    request_id = getattr(
        request.state,
        "request_id",
        None,
    )
    response = JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": "请求过于频繁，请稍后重试",
            "request_id": request_id,
        },
    )
    response.headers["Retry-After"] = str(
        exc.retry_after_seconds
    )
    if request_id:
        response.headers[
            "X-Request-ID"
        ] = request_id
    return response

@app.exception_handler(
    ConversationNotFoundError
)
@app.exception_handler(
    KnowledgeBaseNotFoundError
)
async def relational_resource_not_found_handler(
    request: Request,
    exc: Exception,
):
    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    if isinstance(
        exc,
        ConversationNotFoundError,
    ):
        error = "conversation_not_found"
        message = "指定的会话不存在"
    else:
        error = "knowledge_base_not_found"
        message = "指定的知识库不存在"

    response = JSONResponse(
        status_code=404,
        content={
            "error": error,
            "message": message,
            "request_id": request_id,
        },
    )

    if request_id:
        response.headers[
            "X-Request-ID"
        ] = request_id

    return response


@app.exception_handler(
    ConversationKnowledgeBaseMismatchError
)
async def conversation_mismatch_handler(
    request: Request,
    exc: (
        ConversationKnowledgeBaseMismatchError
    ),
):
    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    response = JSONResponse(
        status_code=409,
        content={
            "error": (
                "conversation_"
                "knowledge_base_mismatch"
            ),
            "message": (
                "会话与指定知识库不匹配"
            ),
            "request_id": request_id,
        },
    )

    if request_id:
        response.headers[
            "X-Request-ID"
        ] = request_id

    return response

@app.exception_handler(
    DocumentReindexConflictError
)
async def document_reindex_conflict_handler(
    request: Request,
    exc: DocumentReindexConflictError,
):
    request_id = getattr(
        request.state,
        "request_id",
        None,
    )
    response = JSONResponse(
        status_code=409,
        content={
            "error": "document_reindex_conflict",
            "message": (
                "文档当前状态不允许重新索引"
            ),
            "request_id": request_id,
        },
    )
    if request_id:
        response.headers[
            "X-Request-ID"
        ] = request_id
    return response


@app.exception_handler(UpstreamServiceError)
async def upstream_service_exception_handler(
    request: Request,
    exc: UpstreamServiceError,
):
    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    response = JSONResponse(
        status_code=502,
        content={
            "error": "upstream_service_error",
            "message": "上游服务暂时不可用，请稍后重试",
            "request_id": request_id,
        },
    )

    if request_id:
        response.headers["X-Request-ID"] = request_id

    return response

@app.exception_handler(UpstreamTimeoutError)
async def upstream_timeout_exception_handler(
    request: Request,
    exc: UpstreamTimeoutError,
):
    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    response = JSONResponse(
        status_code=504,
        content={
            "error": "upstream_timeout",
            "message": "上游服务响应超时，请稍后重试",
            "request_id": request_id,
        },
    )

    if request_id:
        response.headers["X-Request-ID"] = request_id

    return response

@app.exception_handler(Exception)
async def global_exception_handler(
    request: Request,
    exc: Exception,
):
    request_id = getattr(
        request.state,
        "request_id",
        None,
    )

    logger.error(
        "unhandled request failure",
        extra={
            "event": "http_error",
            "request_id": request_id,
            "route": request.url.path,
            "method": request.method,
            "error_code": (
                "internal_server_error"
            ),
        },
    )

    response = JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "服务内部异常",
            "request_id": request_id,
        },
    )

    if request_id:
        response.headers["X-Request-ID"] = request_id

    return response


app.include_router(health_router)
app.include_router(chat_router)
app.include_router(agent_router)

app.include_router(documents_router)
app.include_router(knowledge_bases_router)

app.include_router(
    conversations_router
)

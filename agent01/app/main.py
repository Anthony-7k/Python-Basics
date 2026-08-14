import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes.health import router as health_router
from app.api.routes.chat import router as chat_router


app = FastAPI(
    title="Enterprise Knowledge Agent",
    version="1.0.0",
)


@app.middleware("http")
async def add_request_id(request, call_next):
    request_id = str(uuid.uuid4())

    request.state.request_id = request_id

    response = await call_next(request)

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
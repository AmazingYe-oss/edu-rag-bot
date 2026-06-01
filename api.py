import json
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from prometheus_fastapi_instrumentator import Instrumentator

from src.config import load_config
from src.rag_service import RAGService
from src.memory_manager import RedisMemoryManager
from src.dependencies import init_app_state, lifespan
from src.schemas.common import APIResponse, ErrorDetail
from src.routers import conversations, search, documents


memory_manager = RedisMemoryManager()
config = load_config()
rag_service = RAGService(config)

init_app_state(config, rag_service, memory_manager)

app = FastAPI(
    title="Edu RAG API",
    description="教育知识库 RAG 问答系统 — RESTful API v1",
    lifespan=lifespan,
    version="6.0.0",
    docs_url="/docs",
)

Instrumentator().instrument(app).expose(app)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=APIResponse(
            success=False,
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="请求参数校验失败",
                details=exc.errors(),
            ),
        ).model_dump(),
    )


@app.get("/api/v1/health", tags=["Health"])
async def health_check():
    return APIResponse(data={"status": "healthy", "version": "6.0.0"}).model_dump()


app.include_router(conversations.router)
app.include_router(search.router)
app.include_router(documents.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

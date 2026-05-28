from fastapi import FastAPI, HTTPException,Depends
from pydantic import BaseModel
from src.config import load_config
from src.rag_service import RAGService
import traceback
from prometheus_fastapi_instrumentator import Instrumentator
import chromadb
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import StorageContext
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import os
from contextlib import asynccontextmanager
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[Startup] 正在连接 Redis: {REDIS_URL}")
    redis_conn = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    
    await FastAPILimiter.init(redis_conn)
    print("[Startup] Redis 与限流器初始化成功")
    
    yield  
    
    print("[Shutdown] 正在关闭 Redis 连接...")
    await redis_conn.close()

config = load_config()
rag_service=RAGService(config)

app = FastAPI(
    title="Edu RAG Backend API",
    description="教育大模型问答系统后端接口",
    lifespan=lifespan,
    version="1.0.0"
)

Instrumentator().instrument(app).expose(app)
class ChatRequest(BaseModel):
    question:str

class ChatResponse(BaseModel):
    answer:str
    context:str
@app.post("/api/chat", response_model=ChatResponse,dependencies=[Depends(RateLimiter(times=5, seconds=60))])
def chat_endpoint(request:ChatRequest):
    try:
        answer, context = rag_service.ask(request.question)
        return ChatResponse(answer=answer, context=context)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

    
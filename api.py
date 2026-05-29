import os
import json
import hashlib
import traceback
import time
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv(override=True)

import oss2
# ⚠️ 引入了 Request 和 JSONResponse
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Request
from fastapi.responses import StreamingResponse, JSONResponse
# ⚠️ 引入错误拦截类
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
import redis.asyncio as aioredis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from prometheus_fastapi_instrumentator import Instrumentator
import uuid
from fastapi.concurrency import run_in_threadpool

from src.config import load_config
from src.rag_service import RAGService
from src.memory_manager import RedisMemoryManager

# 全局初始化
memory_manager = RedisMemoryManager()
oss_bucket = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global oss_bucket
    print("[Startup] 正在连接阿里云 Redis (异步限流器)...")
    redis_conn = aioredis.Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD", None),
        db=0,
        encoding="utf-8",
        decode_responses=True
    )
    await FastAPILimiter.init(redis_conn)
    print("[Startup] 🚀 阿里云 Redis 与频控限流器初始化成功")
    print("====== 捉鬼模式 ======")
    print("当前程序拿到的 AK 是: ", config.get("oss_access_key_id"))
    print("======================")

    # 初始化 OSS
    if config.get("oss_access_key_id") and config.get("oss_access_key_secret"):
        print(f"[Startup] OSS 配置: endpoint={config.get('oss_endpoint')}, bucket={config.get('oss_bucket_name')}")
        auth = oss2.Auth(config["oss_access_key_id"], config["oss_access_key_secret"])
        oss_bucket = oss2.Bucket(auth, config["oss_endpoint"], config["oss_bucket_name"])
        print("[Startup] 🚀 阿里云 OSS 初始化成功")
    else:
        print("[Startup] ⚠️ 未配置 OSS，文件上传功能不可用")

    yield
    print("[Shutdown] 正在关闭 Redis 连接...")
    await redis_conn.close()

config = load_config()
rag_service = RAGService(config)

app = FastAPI(
    title="Edu RAG Backend API",
    description="教育大模型问答系统后端接口 (SSE流式 + Redis缓存 完全体)",
    lifespan=lifespan,
    version="5.0.0"
)

Instrumentator().instrument(app).expose(app)

# ==========================================
# 🔍 核心武器：422 错误全局透视拦截器
# ==========================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    print("\n" + "="*50)
    print("❌❌❌ [捉鬼日志] 💥 触发了 422 校验错误！")
    print(f"👉 错误具体原因 (errors): {exc.errors()}")
    print(f"👉 后端收到的原始请求体 (body): {exc.body}")
    print("="*50 + "\n")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": str(exc.body)}
    )

class ChatRequest(BaseModel):
    question: str
    session_id: str = "default_session"

def generate_cache_key(question: str) -> str:
    """生成问题专属的 Redis 缓存指纹 (MD5)"""
    return "rag:cache:" + hashlib.md5(question.encode("utf-8")).hexdigest()

# 核心问答接口
@app.post("/api/chat", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def chat_endpoint(request: Request, payload: ChatRequest): # ⚠️ 显式加上 request，把业务数据隔离到 payload
    question = payload.question.strip()
    session_id = payload.session_id

    # ==========================================
    # 🧱 第 1 道防线：Redis 精确缓存拦截
    # ==========================================
    cache_key = generate_cache_key(question)
    cached_answer = memory_manager.redis_client.get(cache_key)

    if cached_answer:
        def cache_stream():
            payload_data = {"delta": cached_answer, "context": "⚡ 命中 Redis 阿里云缓存，本次查询零费用！"}
            yield f"data: {json.dumps(payload_data, ensure_ascii=False)}\n\n"
        return StreamingResponse(cache_stream(), media_type="text/event-stream")

    # ==========================================
    # 🧠 第 2 步：提取短期历史记忆
    # ==========================================
    history = memory_manager.get_history(session_id)
    if history:
        history_lines = [f"{msg['role']}: {msg['content']}" for msg in history]
        full_question = "【前情提要：历史对话】\n" + "\n".join(history_lines) + "\n\n【新问题】\n" + question
    else:
        full_question = question

    # ==========================================
    # 🌊 第 3 步：定义 SSE 流式打字机生成器
    # ==========================================
    def event_generator():
        try:
            response_gen, retrieved_context = rag_service.stream_ask(full_question)
            full_answer = ""

            for chunk in response_gen:
                delta = chunk.delta
                if delta:
                    full_answer += delta
                    payload_data = {"delta": delta, "context": retrieved_context}
                    yield f"data: {json.dumps(payload_data, ensure_ascii=False)}\n\n"

            if full_answer:
                memory_manager.add_message(session_id, "user", question)
                memory_manager.add_message(session_id, "assistant", full_answer)
                memory_manager.redis_client.setex(cache_key, 3600, full_answer)

        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if oss_bucket is None:
        raise HTTPException(status_code=503, detail="OSS 未配置，无法上传文件")

    ext = file.filename.split('.')[-1] if '.' in file.filename else ''
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    oss_key = f"public/{unique_filename}"

    try:
        content = await file.read()
        import asyncio
        await asyncio.to_thread(oss_bucket.put_object, oss_key, content)
        file_url = f"https://{config['oss_bucket_name']}.{config['oss_endpoint']}/{oss_key}"

        return {
            "original_name": file.filename,
            "oss_filename": oss_key,
            "url": file_url
        }
    except oss2.exceptions.AccessDenied as e:
        traceback.print_exc()
        raise HTTPException(status_code=403, detail="OSS 访问被拒绝，请检查权限设置。")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"上传到 OSS 失败: {str(e)}")

@app.post("/api/upload/presigned")
async def get_presigned_upload_url(filename: str = None):
    if oss_bucket is None:
        raise HTTPException(status_code=503, detail="OSS 未配置，无法生成上传链接")

    ext = filename.split('.')[-1] if '.' in filename else '' if filename else ''
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    oss_key = f"public/{unique_filename}"

    try:
        import asyncio
        presigned_url = await asyncio.to_thread(oss_bucket.sign_url, 'PUT', oss_key, 300)
        return {
            "upload_url": presigned_url,
            "oss_filename": oss_key,
            "expires_in_seconds": 300
        }
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成预签名 URL 失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

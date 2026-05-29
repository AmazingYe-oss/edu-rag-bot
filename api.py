import os
import json
import hashlib
import traceback
import time
from contextlib import asynccontextmanager
from dotenv import load_dotenv

load_dotenv()

import oss2
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import redis.asyncio as aioredis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from prometheus_fastapi_instrumentator import Instrumentator

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

    # 初始化 OSS
    if config.get("oss_access_key_id") and config.get("oss_access_key_secret"):
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

class ChatRequest(BaseModel):
    question: str
    session_id: str = "default_session"

def generate_cache_key(question: str) -> str:
    """生成问题专属的 Redis 缓存指纹 (MD5)"""
    return "rag:cache:" + hashlib.md5(question.encode("utf-8")).hexdigest()

# 核心问答接口 (改为返回 StreamingResponse)
@app.post("/api/chat", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def chat_endpoint(request: ChatRequest):
    question = request.question.strip()
    session_id = request.session_id
    
    # ==========================================
    # 🧱 第 1 道防线：Redis 精确缓存拦截 (省钱省时)
    # ==========================================
    cache_key = generate_cache_key(question)
    cached_answer = memory_manager.redis_client.get(cache_key)
    
    if cached_answer:
        # 如果命中缓存，伪装成流式输出，瞬间吐出答案
        def cache_stream():
            payload = {"delta": cached_answer, "context": "⚡ 命中 Redis 阿里云缓存，本次查询零费用！"}
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
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
            # 调用新增的流式入口
            response_gen, retrieved_context = rag_service.stream_ask(full_question)
            full_answer = ""
            
            # 实时捕获大模型吐出的每一个字，并通过 yield 抛给前端
            for chunk in response_gen:
                delta = chunk.delta
                if delta:
                    full_answer += delta
                    # 标准的 Server-Sent Events 格式: data: {...}\n\n
                    payload = {"delta": delta, "context": retrieved_context}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            
            # 📝 对话全部生成完毕后，写入记忆和缓存
            if full_answer:
                # 存入对话上下文
                memory_manager.add_message(session_id, "user", question)
                memory_manager.add_message(session_id, "assistant", full_answer)
                # 存入全局缓存 (有效期 1 小时，下次有人问同样问题直接白嫖)
                memory_manager.redis_client.setex(cache_key, 3600, full_answer)
                
        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    # 返回流式响应体
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# 文件上传接口
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if oss_bucket is None:
        raise HTTPException(status_code=503, detail="OSS 未配置，无法上传文件")

    # 读取文件内容
    content = await file.read()
    # 生成唯一文件名（使用时间戳 + 原始文件名）
    unique_filename = f"{int(time.time())}_{file.filename}"
    # 上传到 OSS
    try:
        oss_bucket.put_object(unique_filename, content)
        # 生成文件 URL（根据 endpoint 和 bucket 构造）
        file_url = f"https://{config['oss_bucket_name']}.{config['oss_endpoint']}/{unique_filename}"
        return {"filename": unique_filename, "url": file_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

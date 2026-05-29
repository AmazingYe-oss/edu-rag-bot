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

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    if oss_bucket is None:
        raise HTTPException(status_code=503, detail="OSS 未配置，无法上传文件")

    # 1. 解决撞车：使用 UUID 生成绝对唯一的文件名
    ext = file.filename.split('.')[-1] if '.' in file.filename else ''
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    # 文件存储在 public/ 文件夹下
    oss_key = f"public/{unique_filename}"

    try:
        # 2. 读取文件内容（必须读取，因为 oss2.put_object 需要 bytes）
        content = await file.read()
        
        # 3. 直接调用 put_object（同步方法，但 FastAPI 异步端点中直接调用会阻塞，但可以工作）
        # 使用 asyncio.to_thread 避免阻塞主线程
        import asyncio
        await asyncio.to_thread(oss_bucket.put_object, oss_key, content)

        # 4. 构造返回 URL
        file_url = f"https://{config['oss_bucket_name']}.{config['oss_endpoint']}/{oss_key}"
        
        return {
            "original_name": file.filename,
            "oss_filename": oss_key, 
            "url": file_url
        }
    except oss2.exceptions.AccessDenied as e:
        import traceback
        traceback.print_exc()
        print(f"[Upload Error] OSS endpoint: {config.get('oss_endpoint')}, bucket: {config.get('oss_bucket_name')}")
        raise HTTPException(
            status_code=403,
            detail="OSS 访问被拒绝，请检查 AccessKey 权限或 Bucket 权限设置。"
        )
    except Exception as e:
        # 打印详细错误日志
        import traceback
        traceback.print_exc()
        # 打印 OSS 配置信息（不包含密钥）
        print(f"[Upload Error] OSS endpoint: {config.get('oss_endpoint')}, bucket: {config.get('oss_bucket_name')}")
        raise HTTPException(status_code=500, detail=f"上传到 OSS 失败: {str(e)}")


@app.post("/api/upload/presigned")
async def get_presigned_upload_url(filename: str = None):
    """
    生成预签名上传 URL，用户可直接使用该 URL 上传文件到 OSS。
    """
    if oss_bucket is None:
        raise HTTPException(status_code=503, detail="OSS 未配置，无法生成上传链接")

    # 生成唯一文件名
    if filename:
        ext = filename.split('.')[-1] if '.' in filename else ''
    else:
        ext = ''
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    # 文件存储在 public/ 文件夹下
    oss_key = f"public/{unique_filename}"

    try:
        # 生成预签名 URL，有效期 5 分钟（300 秒）
        import asyncio
        presigned_url = await asyncio.to_thread(
            oss_bucket.sign_url,
            'PUT',
            oss_key,
            300  # 有效期（秒）
        )

        return {
            "upload_url": presigned_url,
            "oss_filename": oss_key,
            "expires_in_seconds": 300
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成预签名 URL 失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

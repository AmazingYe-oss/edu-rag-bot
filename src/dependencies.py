import os
from contextlib import asynccontextmanager

import oss2
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi_limiter import FastAPILimiter
from dotenv import load_dotenv

load_dotenv(override=True)

config: dict = {}
rag_service = None
memory_manager = None
oss_bucket = None


def init_app_state(_config, _rag_service, _memory_manager):
    global config, rag_service, memory_manager
    config = _config
    rag_service = _rag_service
    memory_manager = _memory_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    global oss_bucket

    redis_conn = aioredis.Redis(
        host=os.getenv("REDIS_HOST", "127.0.0.1"),
        port=int(os.getenv("REDIS_PORT", 6379)),
        password=os.getenv("REDIS_PASSWORD", None),
        db=0,
        encoding="utf-8",
        decode_responses=True,
    )
    await FastAPILimiter.init(redis_conn)

    if config.get("oss_access_key_id") and config.get("oss_access_key_secret"):
        auth = oss2.Auth(config["oss_access_key_id"], config["oss_access_key_secret"])
        oss_bucket = oss2.Bucket(auth, config["oss_endpoint"], config["oss_bucket_name"])
        print("[Startup] 🚀 OSS + Redis 初始化完成")
    else:
        print("[Startup] ⚠️ 未配置 OSS，文件上传功能不可用")

    yield

    await redis_conn.close()
    print("[Shutdown] Redis 连接已关闭")

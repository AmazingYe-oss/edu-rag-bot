import json
import redis
import os
from dotenv import load_dotenv

# 强制优先加载环境变量
load_dotenv()

class RedisMemoryManager:
    def __init__(self):
        redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
        redis_port = int(os.getenv("REDIS_PORT", 6379))
        redis_password = os.getenv("REDIS_PASSWORD", None)
        
        # 传入 password 参数直连阿里云，完美规避特殊字符 bug
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            password=redis_password,
            db=0, 
            decode_responses=True
        )
        # 会话过期时间：86400秒 (24小时)
        self.session_ttl = 86400 

    def get_history(self, session_id: str, k: int = 3) -> list:
        key = f"rag:memory:{session_id}"
        raw_history = self.redis_client.lrange(key, -(k * 2), -1)
        
        if not raw_history:
            return []
            
        return [json.loads(msg) for msg in raw_history]

    def add_message(self, session_id: str, role: str, content: str):
        key = f"rag:memory:{session_id}"
        msg_dict = {"role": role, "content": content}
        
        self.redis_client.rpush(key, json.dumps(msg_dict, ensure_ascii=False))
        self.redis_client.expire(key, self.session_ttl)
        
    def clear_memory(self, session_id: str):
        self.redis_client.delete(f"rag:memory:{session_id}")

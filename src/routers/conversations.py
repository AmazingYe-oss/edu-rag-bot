import json
import hashlib
import traceback
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import StreamingResponse
from fastapi_limiter.depends import RateLimiter

from src.dependencies import rag_service, memory_manager
from src.schemas.conversation import (
    ConversationCreateRequest,
    ConversationCreateResponse,
    MessageRequest,
)

router = APIRouter(prefix="/api/v1/conversations", tags=["Conversations"])


def _cache_key(question: str) -> str:
    return "rag:cache:" + hashlib.md5(question.encode("utf-8")).hexdigest()


@router.post("", response_model=ConversationCreateResponse, status_code=201)
async def create_conversation(body: ConversationCreateRequest = ConversationCreateRequest()):
    conversation_id = uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    return ConversationCreateResponse(
        conversation_id=conversation_id,
        title=body.title or "新会话",
        created_at=now,
    )


@router.post(
    "/{conversation_id}/messages",
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
)
async def send_message(conversation_id: str, body: MessageRequest):
    question = body.content.strip()
    if not question:
        raise HTTPException(status_code=400, detail="消息内容不能为空")

    cache_hit_key = _cache_key(question)
    cached = memory_manager.redis_client.get(cache_hit_key)

    if cached:
        def cache_stream():
            yield f"data: {json.dumps({'delta': cached, 'context': '⚡ Redis 缓存命中，零费用！'}, ensure_ascii=False)}\n\n"
        return StreamingResponse(cache_stream(), media_type="text/event-stream")

    history = memory_manager.get_history(conversation_id)
    if history:
        lines = [f"{m['role']}: {m['content']}" for m in history]
        full_question = "【前情提要：历史对话】\n" + "\n".join(lines) + "\n\n【新问题】\n" + question
    else:
        full_question = question

    def event_generator():
        try:
            # 传递 user_id 以实现检索隔离
            gen, ctx = rag_service.stream_ask(full_question, body.user_id)
            answer = ""
            ctx_sent = False
            for chunk in gen:
                delta = chunk.delta
                if delta:
                    answer += delta
                    payload = {"delta": delta}
                    if not ctx_sent:
                        payload["context"] = ctx
                        ctx_sent = True
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            if answer:
                memory_manager.add_message(conversation_id, "user", question)
                memory_manager.add_message(conversation_id, "assistant", answer)
                memory_manager.redis_client.setex(cache_hit_key, 3600, answer)
        except Exception as e:
            traceback.print_exc()
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/{conversation_id}/messages")
async def get_messages(conversation_id: str):
    history = memory_manager.get_history(conversation_id)
    return {
        "conversation_id": conversation_id,
        "messages": history,
        "count": len(history) if history else 0,
    }

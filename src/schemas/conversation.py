from pydantic import BaseModel, Field


class ConversationCreateRequest(BaseModel):
    title: str | None = Field(default=None, description="会话标题(可选)", max_length=200)


class ConversationCreateResponse(BaseModel):
    conversation_id: str = Field(..., description="新创建的会话唯一标识")
    title: str = Field(default="新会话", description="会话标题")
    created_at: str = Field(..., description="创建时间 ISO-8601")


class MessageRequest(BaseModel):
    content: str = Field(..., description="用户消息内容", min_length=1, max_length=50000)
    user_id: str | None = Field(None, description="租户/用户唯一标识，用于隔离检索")


class MessageSSEEvent(BaseModel):
    delta: str = Field(default="", description="增量文本片段")
    context: str | None = Field(default=None, description="检索上下文(仅首条携带)")


class MessageHistoryItem(BaseModel):
    role: str = Field(..., description="消息角色: user/assistant")
    content: str = Field(..., description="消息内容")


class MessageHistoryResponse(BaseModel):
    conversation_id: str = Field(..., description="会话 ID")
    messages: list[MessageHistoryItem] = Field(default_factory=list, description="历史消息列表")
    count: int = Field(default=0, description="消息条数")

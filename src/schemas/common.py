from pydantic import BaseModel, Field
from typing import Any


class ErrorDetail(BaseModel):
    code: str = Field(..., description="机器可读错误码")
    message: str = Field(..., description="人类可读错误描述")
    details: list[Any] | None = Field(default=None, description="详细错误列表")


class APIResponse(BaseModel):
    success: bool = Field(default=True, description="是否成功")
    data: Any | None = Field(default=None, description="响应数据")
    error: ErrorDetail | None = Field(default=None, description="错误信息(仅失败时)")

from pydantic import BaseModel, Field


class DocumentUploadRequest(BaseModel):
    user_id: str = Field(..., description="租户/用户唯一标识", min_length=1)


class PresignedUrlRequest(BaseModel):
    filename: str = Field(..., description="原始文件名(用于确定扩展名)", min_length=1, max_length=500)


class PresignedUrlResponse(BaseModel):
    upload_url: str = Field(..., description="预签名 PUT 上传地址")
    document_key: str = Field(..., description="OSS 上的对象 Key")
    expires_in_seconds: int = Field(default=300, description="链接有效期(秒)")


class DocumentUploadResponse(BaseModel):
    document_id: str = Field(..., description="存储中的唯一标识")
    filename: str = Field(..., description="原始文件名")
    url: str = Field(..., description="OSS 访问地址")
    indexed: bool = Field(..., description="是否已向量化入库")
    index_message: str = Field(..., description="入库结果描述")
    summary: str | None = Field(None, description="文档全局摘要")


class BatchUploadResponse(BaseModel):
    total: int = Field(..., description="上传文件总数")
    success_count: int = Field(..., description="成功入库文件数")
    failed_count: int = Field(..., description="失败文件数")
    results: list[DocumentUploadResponse] = Field(..., description="每个文件的处理结果")

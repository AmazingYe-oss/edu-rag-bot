import os
import uuid
import tempfile
import traceback
from pathlib import Path

import oss2
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool

from src.dependencies import rag_service, oss_bucket, config
from src.schemas.document import (
    PresignedUrlRequest,
    PresignedUrlResponse,
    DocumentUploadResponse,
)

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(file: UploadFile = File(...)):
    if oss_bucket is None:
        raise HTTPException(status_code=503, detail="OSS 未配置，无法上传文件")

    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else ""
    doc_id = uuid.uuid4().hex
    oss_key = f"public/{doc_id}.{ext}" if ext else f"public/{doc_id}"

    try:
        content = await file.read()
        import asyncio
        await asyncio.to_thread(oss_bucket.put_object, oss_key, content)
        file_url = f"https://{config['oss_bucket_name']}.{config['oss_endpoint']}/{oss_key}"

        suffix = f".{ext}" if ext else ""
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            metadata = await run_in_threadpool(rag_service.insert_document, Path(tmp_path))
            indexed = True
            index_msg = f"已入库，来源: {metadata.get('file_name', doc_id)}"
        except ValueError as ve:
            indexed = False
            index_msg = str(ve)
        except Exception as ie:
            traceback.print_exc()
            indexed = False
            index_msg = f"向量化入库失败: {str(ie)}"
        finally:
            os.unlink(tmp_path)

        return DocumentUploadResponse(
            document_id=doc_id,
            filename=file.filename,
            url=file_url,
            indexed=indexed,
            index_message=index_msg,
        )
    except oss2.exceptions.AccessDenied:
        raise HTTPException(status_code=403, detail="OSS 访问被拒绝，请检查权限设置")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"上传到 OSS 失败: {str(e)}")


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def get_presigned_url(body: PresignedUrlRequest):
    if oss_bucket is None:
        raise HTTPException(status_code=503, detail="OSS 未配置，无法生成上传链接")

    filename = body.filename
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    doc_id = uuid.uuid4().hex
    oss_key = f"public/{doc_id}.{ext}" if ext else f"public/{doc_id}"

    try:
        import asyncio
        presigned_url = await asyncio.to_thread(oss_bucket.sign_url, "PUT", oss_key, 300)
        return PresignedUrlResponse(
            upload_url=presigned_url,
            document_key=oss_key,
            expires_in_seconds=300,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成预签名 URL 失败: {str(e)}")

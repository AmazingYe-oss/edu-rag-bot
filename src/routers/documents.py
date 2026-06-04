import os
import uuid
import tempfile
import traceback
import asyncio
from pathlib import Path
from datetime import datetime
from typing import List

import oss2
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.concurrency import run_in_threadpool

import src.dependencies as deps
from src.schemas.document import (
    DocumentUploadRequest,
    PresignedUrlRequest,
    PresignedUrlResponse,
    DocumentUploadResponse,
    BatchUploadResponse,
)

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


@router.post("", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    user_id: str = Form(...), 
    file: UploadFile = File(...)
):
    if deps.oss_bucket is None:
        raise HTTPException(status_code=503, detail="OSS 未配置，无法上传文件")

    # 1. OSS 多租户物理隔离路径拼接
    current_date = datetime.now().strftime("%Y-%m-%d")
    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else ""
    doc_id = uuid.uuid4().hex
    oss_key = f"users/{user_id}/documents/{current_date}/{doc_id}.{ext}" if ext else f"users/{user_id}/documents/{current_date}/{doc_id}"

    try:
        content = await file.read()
        import asyncio
        await asyncio.to_thread(deps.oss_bucket.put_object, oss_key, content)
        file_url = f"https://{deps.config['oss_bucket_name']}.{deps.config['oss_endpoint']}/{oss_key}"

        suffix = f".{ext}" if ext else ""
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        summary = None
        try:
            # 2. 调用 RAG 2.0 异步入库流程（含摘要生成与 Metadata 绑定）
            result = await deps.rag_service.insert_document_v2(Path(tmp_path), user_id)
            indexed = True
            index_msg = f"已入库 ({result.get('chunks_count', 0)} 个切片)"
            summary = result.get('summary')
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
            summary=summary,
        )
    except oss2.exceptions.AccessDenied:
        raise HTTPException(status_code=403, detail="OSS 访问被拒绝，请检查权限设置")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"上传到 OSS 失败: {str(e)}")


@router.post("/presigned-url", response_model=PresignedUrlResponse)
async def get_presigned_url(body: PresignedUrlRequest):
    if deps.oss_bucket is None:
        raise HTTPException(status_code=503, detail="OSS 未配置，无法生成上传链接")

    filename = body.filename
    ext = filename.rsplit(".", 1)[-1] if "." in filename else ""
    doc_id = uuid.uuid4().hex
    oss_key = f"public/{doc_id}.{ext}" if ext else f"public/{doc_id}"

    try:
        import asyncio
        presigned_url = await asyncio.to_thread(deps.oss_bucket.sign_url, "PUT", oss_key, 300)
        return PresignedUrlResponse(
            upload_url=presigned_url,
            document_key=oss_key,
            expires_in_seconds=300,
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"生成预签名 URL 失败: {str(e)}")


async def _process_single_file(
    user_id: str,
    file: UploadFile,
    current_date: str,
) -> DocumentUploadResponse:
    """
    处理单个文件的上传与入库（辅助函数，供批量上传复用）。
    """
    ext = file.filename.rsplit(".", 1)[-1] if "." in (file.filename or "") else ""
    doc_id = uuid.uuid4().hex
    oss_key = f"users/{user_id}/documents/{current_date}/{doc_id}.{ext}" if ext else f"users/{user_id}/documents/{current_date}/{doc_id}"

    try:
        content = await file.read()
        await asyncio.to_thread(deps.oss_bucket.put_object, oss_key, content)
        file_url = f"https://{deps.config['oss_bucket_name']}.{deps.config['oss_endpoint']}/{oss_key}"

        suffix = f".{ext}" if ext else ""
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        summary = None
        try:
            result = await deps.rag_service.insert_document_v2(Path(tmp_path), user_id)
            indexed = True
            index_msg = f"已入库 ({result.get('chunks_count', 0)} 个切片)"
            summary = result.get('summary')
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
            summary=summary,
        )
    except Exception as e:
        traceback.print_exc()
        return DocumentUploadResponse(
            document_id=doc_id,
            filename=file.filename,
            url="",
            indexed=False,
            index_message=f"上传失败: {str(e)}",
            summary=None,
        )


@router.post("/batch", response_model=BatchUploadResponse, status_code=201)
async def batch_upload_documents(
    user_id: str = Form(...),
    files: List[UploadFile] = File(...),
):
    """
    批量上传多个文件并入库（最多 10 个文件）。
    """
    if deps.oss_bucket is None:
        raise HTTPException(status_code=503, detail="OSS 未配置，无法上传文件")

    if len(files) > 10:
        raise HTTPException(status_code=400, detail="每次最多上传 10 个文件")

    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一个文件")

    current_date = datetime.now().strftime("%Y-%m-%d")

    # 并行处理所有文件上传
    tasks = [_process_single_file(user_id, file, current_date) for file in files]
    results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r.indexed)
    failed_count = len(results) - success_count

    return BatchUploadResponse(
        total=len(results),
        success_count=success_count,
        failed_count=failed_count,
        results=list(results),
    )

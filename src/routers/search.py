import traceback
from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from src.dependencies import rag_service
from src.schemas.search import SearchRequest, SearchResponse, SearchResultItem

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


@router.post("", response_model=SearchResponse)
async def search(body: SearchRequest):
    try:
        results_raw = await run_in_threadpool(rag_service.retrieve, body.query)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

    items = [
        SearchResultItem(
            index=r["index"],
            content=r["content"],
            file_name=r["file_name"],
            file_type=r["file_type"],
            score=r.get("score"),
        )
        for r in (results_raw[: body.top_k] if results_raw else [])
    ]
    return SearchResponse(query=body.query, results=items, count=len(items))

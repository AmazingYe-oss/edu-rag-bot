from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(..., description="检索查询语句", min_length=1, max_length=50000)
    top_k: int = Field(default=3, description="返回 Top-K 结果数", ge=1, le=20)


class SearchResultItem(BaseModel):
    index: int = Field(..., description="排名序号")
    content: str = Field(..., description="检索到的文本片段")
    file_name: str = Field(default="未知文件", description="来源文件名")
    file_type: str = Field(default="", description="文件类型扩展名")
    score: float | None = Field(default=None, description="相似度分数")


class SearchResponse(BaseModel):
    query: str = Field(..., description="原始查询语句")
    results: list[SearchResultItem] = Field(default_factory=list, description="检索结果列表")
    count: int = Field(default=0, description="结果总数")

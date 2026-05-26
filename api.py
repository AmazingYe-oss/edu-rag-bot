from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from src.config import load_config
from src.rag_service import RAGService
import traceback
from prometheus_fastapi_instrumentator import Instrumentator

config = load_config()
rag_service=RAGService(config)

app = FastAPI(
    title="Edu RAG Backend API",
    description="教育大模型问答系统后端接口",
    version="1.0.0"
)

Instrumentator().instrument(app).expose(app)
class ChatRequest(BaseModel):
    question:str

class ChatResponse(BaseModel):
    answer:str
    context:str
@app.post("/api/chat", response_model=ChatResponse)
def chat_endpoint(request:ChatRequest):
    try:
        answer, context = rag_service.ask(request.question)
        return ChatResponse(answer=answer, context=context)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

    
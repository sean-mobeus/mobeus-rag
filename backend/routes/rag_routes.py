from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from rag.retriever import query_rag

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"service": "rag", "status": "healthy"}


class QueryRequest(BaseModel):
    uuid: str
    query: str


@router.post("/query")
async def rag_query(payload: QueryRequest):
    """
    Query the RAG retriever with user-provided query and session UUID.
    """
    try:
        return query_rag(payload.query, payload.uuid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

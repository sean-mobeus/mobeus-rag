from fastapi import APIRouter, HTTPException

from memory.client import MemoryClient
from memory.models import (
    ClearMemoryRequest,
    ClearMemoryResponse,
    MemoryClearStats,
    SessionDataResponse,
    PromptStorageResponse,
    ConversationDataResponse,
    AppendSummaryRequest,
    AppendSummaryResponse,
)

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"service": "memory", "status": "healthy"}


client = MemoryClient()


@router.post("/clear", response_model=ClearMemoryResponse)
async def clear_memory(payload: ClearMemoryRequest):
    uuid = payload.uuid
    session_size = client.get_session_size(uuid)
    conversation = client.get_session(uuid)
    session_messages = len(conversation)
    persistent_summary = client.get_summary(uuid) or ""
    persistent_size = len(persistent_summary)

    client.clear_session(uuid)
    client.clear_summary(uuid)

    stats = MemoryClearStats(
        session_messages=session_messages,
        session_chars=session_size,
        persistent_chars=persistent_size,
        total_chars=session_size + persistent_size,
    )
    return ClearMemoryResponse(success=True, cleared=stats)


@router.get("/session/{uuid}", response_model=SessionDataResponse)
async def get_session_data(uuid: str):
    try:
        conversation = client.get_session(uuid)
        summary = client.get_summary(uuid) or ""
        return SessionDataResponse(
            uuid=uuid,
            conversation_count=len(conversation),
            conversation_preview=conversation[:2],
            summary_length=len(summary),
            summary_preview=summary[:200] if summary else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/prompt-storage/{uuid}", response_model=PromptStorageResponse)
async def get_prompt_storage(uuid: str):
    try:
        debug_result = client.debug_prompt_storage(uuid)
        return PromptStorageResponse(uuid=uuid, debug_result=debug_result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversation-data/{uuid}", response_model=ConversationDataResponse)
async def get_conversation_data(uuid: str):
    try:
        data = client.get_conversation_data(uuid)
        return ConversationDataResponse(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary", response_model=AppendSummaryResponse)
async def append_summary(payload: AppendSummaryRequest):
    try:
        client.append_summary(payload.uuid, payload.info)
        return AppendSummaryResponse(success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

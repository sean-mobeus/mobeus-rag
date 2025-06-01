from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ClearMemoryRequest(BaseModel):
    uuid: str


class MemoryClearStats(BaseModel):
    session_messages: int
    session_chars: int
    persistent_chars: int
    total_chars: int


class ClearMemoryResponse(BaseModel):
    success: bool
    cleared: MemoryClearStats


class SessionDataResponse(BaseModel):
    uuid: str
    conversation_count: int
    conversation_preview: List[Dict[str, Any]]
    summary_length: int
    summary_preview: Optional[str]


class PromptStorageResponse(BaseModel):
    uuid: str
    debug_result: Any


class ConversationDataResponse(BaseModel):
    uuid: str
    current_session_count: int
    current_session_preview: List[Dict[str, Any]]
    historical_interactions_count: int
    historical_interactions_preview: List[Dict[str, Any]]


class AppendSummaryRequest(BaseModel):
    uuid: str
    info: str

class AppendSummaryResponse(BaseModel):
    success: bool


class UserModel(BaseModel):
    uuid: str
    name: Optional[str]
    created_at: Optional[str]
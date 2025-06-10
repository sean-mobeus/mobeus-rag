from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from uuid import uuid4

from video.processor import get_video_processor

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"service": "video", "status": "healthy"}

class CreateStreamRequest(BaseModel):
    source_url: str


class CreateStreamResponse(BaseModel):
    id: str
    session_id: str
    offer: str
    ice_servers: List[Dict[str, Any]]


@router.post("/streams", response_model=CreateStreamResponse)
async def create_stream(request: CreateStreamRequest):
    """
    Initialize a video streaming session (stub).
    """
    processor = get_video_processor()
    stream_id = uuid4().hex
    session_id = uuid4().hex
    return CreateStreamResponse(id=stream_id, session_id=session_id, offer="", ice_servers=[])


class SdpRequest(BaseModel):
    answer: str
    session_id: str


@router.post("/streams/{stream_id}/sdp")
async def send_sdp_answer(stream_id: str, request: SdpRequest):
    """
    Submit SDP answer to the video provider (stub).
    """
    processor = get_video_processor()
    return await processor.send_sdp_answer(stream_id, request.session_id, request.answer)


class IceCandidate(BaseModel):
    candidate: str
    sdpMid: str
    sdpMLineIndex: int
    session_id: str


@router.post("/streams/{stream_id}/ice")
async def add_ice_candidate(stream_id: str, request: IceCandidate):
    """
    Submit ICE candidate for WebRTC handshake (stub).
    """
    processor = get_video_processor()
    await processor.send_ice_candidate(
        stream_id,
        request.session_id,
        {"candidate": request.candidate, "sdpMid": request.sdpMid, "sdpMLineIndex": request.sdpMLineIndex},
    )
    return {"status": "ok"}


class TalkRequest(BaseModel):
    session_id: str
    text: Optional[str] = None
    audio_url: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


@router.post("/streams/{stream_id}")
async def create_talk(stream_id: str, request: TalkRequest):
    """
    Create a talk on the established video stream (stub).
    """
    processor = get_video_processor()
    return await processor.create_talk(stream_id, request.session_id, request.dict())


class CloseStreamRequest(BaseModel):
    session_id: str


@router.delete("/streams/{stream_id}")
async def close_stream(stream_id: str, request: CloseStreamRequest):
    """
    Close the video streaming session (stub).
    """
    processor = get_video_processor()
    await processor.close_stream(stream_id, request.session_id)
    return {"status": "closed"}

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from uuid import uuid4
import time


from video.processor import get_did_video_processor
from config import runtime_config

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
    processor = get_did_video_processor()
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
    processor = get_did_video_processor()
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
    processor = get_did_video_processor()
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
    processor = get_did_video_processor()
    return await processor.create_talk(stream_id, request.session_id, request.dict())


class CloseStreamRequest(BaseModel):
    session_id: str


@router.delete("/streams/{stream_id}")
async def close_stream(stream_id: str, request: CloseStreamRequest):
    """
    Close the video streaming session (stub).
    """
    processor = get_did_video_processor()
    await processor.close_stream(stream_id, request.session_id)
    return {"status": "closed"}

@router.post("/talks/text")
async def create_talk_from_text(request: Dict[str, Any]):
    """Create D-ID talk from text (lower latency)"""
    start_time = time.time()
    
    text = request.get("text")
    if not text:
        raise HTTPException(status_code=400, detail="Text is required")
    
    try:
        async with get_did_video_processor() as processor:
            # Create talk
            talk_data = await processor.create_talk_from_text(
                text=text,
                voice_id=request.get("voice_id") or runtime_config.get("DID_VOICE_ID"),
                voice_provider=request.get("voice_provider") or runtime_config.get("DID_VOICE_PROVIDER"),
                voice_style=request.get("voice_style") or runtime_config.get("DID_VOICE_STYLE"),
                expression=request.get("expression") or runtime_config.get("DID_EXPRESSION")
            )
            
            talk_id = talk_data["id"]
            
            # Poll for completion
            video_url = await processor.wait_for_talk_completion(talk_id)
            
            end_time = time.time()
            latency = end_time - start_time
            
            return {
                "talk_id": talk_id,
                "video_url": video_url,
                "latency": latency,
                "mode": "text"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/talks/audio") 
async def create_talk_from_audio(request: Dict[str, Any]):
    """Create D-ID talk from audio (preserves voice)"""
    start_time = time.time()
    
    audio_base64 = request.get("audio")
    if not audio_base64:
        raise HTTPException(status_code=400, detail="Audio is required")
    
    try:
        async with get_did_video_processor() as processor:
            # Create talk
            talk_data = await processor.create_talk_from_audio(
                audio_base64=audio_base64,
                expression=request.get("expression") or runtime_config.get("DID_EXPRESSION")
            )
            
            talk_id = talk_data["id"]
            
            # Poll for completion
            video_url = await processor.wait_for_talk_completion(talk_id)
            
            end_time = time.time()
            latency = end_time - start_time
            
            return {
                "talk_id": talk_id,
                "video_url": video_url,
                "latency": latency,
                "mode": "audio"
            }
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/talks/{talk_id}/status")
async def get_talk_status(talk_id: str):
    """Get status of a D-ID talk"""
    try:
        async with get_did_video_processor() as processor:
            status = await processor.get_talk_status(talk_id)
            return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

"""
Video processor abstraction over video providers.

Defines interfaces and factory for video provider implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from video.did_streaming_client import DIDStreamingClient
import os
import asyncio
from datetime import datetime
import config.runtime_config as runtime_config


class BaseVideoProcessor(ABC):
    @abstractmethod
    async def create_stream(self, source_url: str) -> Dict[str, Any]:
        """
        Initialize a video streaming session with the given source URL.
        Returns a dict with keys: id, session_id, offer, ice_servers.
        """
        ...

    @abstractmethod
    async def send_sdp_answer(
        self, stream_id: str, session_id: str, answer: str
    ) -> Dict[str, Any]:
        """
        Send SDP answer to complete WebRTC handshake.
        """
        ...

    @abstractmethod
    async def send_ice_candidate(
        self, stream_id: str, session_id: str, candidate: Dict[str, Any]
    ) -> None:
        """
        Send ICE candidate to the provider.
        """
        ...

    @abstractmethod
    async def create_talk(
        self, stream_id: str, session_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a talk request (e.g., text, audio) over the established stream.
        """
        ...

    @abstractmethod
    async def close_stream(self, stream_id: str, session_id: str) -> None:
        """
        Close the video streaming session.
        """
        ...


def get_video_processor(provider_name: Optional[str] = None) -> BaseVideoProcessor:
    """
    Factory to retrieve the configured video processor provider.
    """
    key = provider_name or runtime_config.get("VIDEO_PROVIDER", "d-id")
    if key == "d-id":
        return DIdVideoProcessor()
    raise ValueError(f"Unsupported video processor provider: {key}")


class DIdVideoProcessor(BaseVideoProcessor):
    def __init__(self):
        api_key = os.getenv("DID_API_KEY")
        if not api_key:
            raise ValueError("DID_API_KEY environment variable is required")
        self.client = DIDStreamingClient(api_key)
        self.active_streams = {}  # track stream metadata
        
    async def create_stream(self, source_url: str) -> Dict[str, Any]:
        """Create D-ID stream and return connection info"""
        result = await self.client.create_stream(source_url)
        
        # Store stream metadata
        self.active_streams[result["stream_id"]] = {
            "session_id": result["session_id"],
            "created_at": datetime.now()
        }
        
        # Start ICE gathering
        asyncio.create_task(self.client.handle_ice_gathering(result["stream_id"]))
        
        return {
            "id": result["stream_id"],
            "session_id": result["session_id"],
            "offer": result["answer"],  # We send our answer as the "offer" to frontend
            "ice_servers": result["ice_servers"]
        }

    async def send_sdp_answer(
        self, stream_id: str, session_id: str, answer: str
    ) -> Dict[str, Any]:
        """For D-ID streaming, this is already handled in create_stream"""
        # Since we handle the SDP exchange in create_stream, this is a no-op
        return {"status": "ok"}

    async def send_ice_candidate(
        self, stream_id: str, session_id: str, candidate: Dict[str, Any]
    ) -> None:
        """Forward ICE candidates from frontend to D-ID"""
        await self.client.send_ice_candidate(stream_id, candidate)

    async def create_talk(
        self, stream_id: str, session_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send text to D-ID for avatar speech generation"""
        text = payload.get("text")
        if not text:
            raise ValueError("Text is required for talk creation")
            
        voice_settings = payload.get("config", {}).get("voice", {})
        result = await self.client.send_text(stream_id, text, voice_settings)
        
        if not result:
            raise ValueError("No response received from send_text")
        
        return {
            "status": "ok",
            "talk_id": result.get("id"),
            "duration": result.get("duration")
        }

    async def close_stream(self, stream_id: str, session_id: str) -> None:
        """Close D-ID stream"""
        await self.client.close_stream(stream_id)
        
        # Clean up metadata
        if stream_id in self.active_streams:
            del self.active_streams[stream_id]
"""
Video processor abstraction over video providers.

Defines interfaces and factory for video provider implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

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
    async def create_stream(self, source_url: str) -> Dict[str, Any]:
        raise NotImplementedError("D-ID video create_stream not implemented")

    async def send_sdp_answer(
        self, stream_id: str, session_id: str, answer: str
    ) -> Dict[str, Any]:
        raise NotImplementedError("D-ID video send_sdp_answer not implemented")

    async def send_ice_candidate(
        self, stream_id: str, session_id: str, candidate: Dict[str, Any]
    ) -> None:
        raise NotImplementedError("D-ID video send_ice_candidate not implemented")

    async def create_talk(
        self, stream_id: str, session_id: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        raise NotImplementedError("D-ID video create_talk not implemented")

    async def close_stream(self, stream_id: str, session_id: str) -> None:
        raise NotImplementedError("D-ID video close_stream not implemented")
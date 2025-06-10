"""
Video processor abstraction over video providers.

Defines interfaces and factory for video provider implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import asyncio
import httpx
import base64
import json
import struct
import io
from datetime import datetime

import config, time
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
    
    async def __aenter__(self):
        """Async context manager entry"""
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        pass

def get_did_video_processor() -> 'DIdVideoProcessor':
    """Get D-ID video processor with proper type hints"""
    return DIdVideoProcessor()

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
    
    def __init__(self):
        self.api_key = config.DID_API_KEY
        self.base_url = runtime_config.get("DID_API_BASE_URL", "https://api.d-id.com")
        self.headers = {
            "Authorization": f"Basic {self.api_key}",
            "Content-Type": "application/json"
        }
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    # --- HTTP /talks API methods ---
    
    async def create_talk_from_text(
        self, 
        text: str,
        source_url: Optional[str] = None,
        voice_id: Optional[str] = None,
        voice_provider: str = "microsoft",
        voice_style: Optional[str] = None,
        expression: Optional[str] = None,
        webhook_url: Optional[str] = None,
        talk_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a talk video from text using D-ID /talks API
        """
        source_url = source_url or runtime_config.get("DID_AVATAR_SOURCE_URL")
        voice_id = voice_id or runtime_config.get("DID_VOICE_ID", "en-US-JennyNeural")

        # Generate a unique talk ID if not provided
        if not talk_id:
            import uuid
            talk_id = f"tlk_{uuid.uuid4().hex[:12]}"
    
        # Use your backend webhook endpoint
        if not webhook_url:
            backend_base = runtime_config.get("BACKEND_WEBHOOK_URL", "http://backend:8010")
            print(f"🔍 DEBUG: BACKEND_WEBHOOK_URL = {backend_base}")
            webhook_url = f"{backend_base}/webhooks/did/{talk_id}"

        payload = {
            "source_url": source_url,
            "webhook": webhook_url,
            "script": {
                "type": "text",
                "input": text,
                "provider": {
                    "type": voice_provider,
                    "voice_id": voice_id
                }
            }
        }
        
        if voice_style and voice_provider == "microsoft":
            payload["script"]["provider"]["voice_config"] = {
                "style": voice_style
            }
        
        if expression:
            payload["config"] = {
                "driver_expressions": {
                    "expressions": [{
                        "expression": expression, 
                        "start_frame": 0,
                        "intensity": 1.0  # Add this - required by D-ID (0.0 to 1.0)
                    }]
                }
            }
            
        if webhook_url:
            payload["webhook"] = webhook_url
            
        if "config" not in payload:
            payload["config"] = {}
        payload["config"]["stitch"] = runtime_config.get("DID_STITCH", True)
        
        print(f"🎬 Creating D-ID talk from text: {text[:50]}...")
        
        response = await self.client.post(
            f"{self.base_url}/talks",
            json=payload,
            headers=self.headers
        )
        
        if response.status_code != 201:
            raise Exception(f"D-ID API error: {response.status_code} - {response.text}")
            
        data = response.json()
        data["webhook_talk_id"] = talk_id
        print(f"✅ D-ID talk created: {data['id']} (webhook ID: {talk_id})")
        return data
    
    async def create_talk_from_audio(
        self,
        audio_base64: str,
        source_url: Optional[str] = None,
        expression: Optional[str] = None,
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a talk video from audio (preserves OpenAI voice)
        """
        source_url = source_url or runtime_config.get("DID_AVATAR_SOURCE_URL")
        
        payload = {
            "source_url": source_url,
            "script": {
                "type": "audio",
                "audio": audio_base64
            }
        }
        
        if expression:
            payload["config"] = {
                "driver_expressions": {
                    "expressions": [{
                        "expression": expression, 
                        "start_frame": 0,
                        "intensity": 1.0  # Add this
                    }]
                }
            }
            
        if webhook_url:
            payload["webhook"] = webhook_url
            
        if "config" not in payload:
            payload["config"] = {}
        payload["config"]["stitch"] = runtime_config.get("DID_STITCH", True)
        
        print(f"🎬 Creating D-ID talk from audio (length: {len(audio_base64)} chars)")
        
        response = await self.client.post(
            f"{self.base_url}/talks",
            json=payload,
            headers=self.headers
        )
        
        if response.status_code != 201:
            raise Exception(f"D-ID API error: {response.status_code} - {response.text}")
            
        data = response.json()
        print(f"✅ D-ID talk created from audio: {data['id']}")
        return data
    
    async def get_talk_status(self, talk_id: str) -> Dict[str, Any]:
        """
        Get the status of a talk video
        """
        response = await self.client.get(
            f"{self.base_url}/talks/{talk_id}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            raise Exception(f"D-ID API error: {response.status_code} - {response.text}")
            
        return response.json()
    
    async def wait_for_talk_completion(
        self, 
        talk_id: str, 
        max_retries: int = 30,
        delay: float = 0.5
    ) -> Optional[str]:
        """
        Wait for talk completion via webhook (fast) or polling (fallback)
        """
        print(f"⏳ Waiting for talk {talk_id} via webhook...")
        
        # Import here to avoid circular imports
        from routes.webhooks import create_webhook_queue
        
        # Create queue and wait for webhook
        queue = create_webhook_queue(talk_id)
        
        try:
            # Wait up to 15 seconds for webhook
            result = await asyncio.wait_for(queue.get(), timeout=15.0)
            
            if result.get("status") == "done":
                video_url = result.get("result_url")
                print(f"✅ Talk completed via webhook: {video_url}")
                return video_url
            elif result.get("status") == "error":
                error_msg = result.get("error", {}).get("message", "Unknown error")
                raise Exception(f"D-ID webhook error: {error_msg}")
                
        except asyncio.TimeoutError:
            print("⚠️ Webhook timeout, falling back to polling...")
        
        # Fallback to polling
        await asyncio.sleep(0.2)  # Small initial delay

        for attempt in range(max_retries):
            try:
                status_data = await self.get_talk_status(talk_id)
                status = status_data.get("status")
                
                if status == "done":
                    video_url = status_data.get("result_url")
                    print(f"✅ Talk completed via polling: {video_url}")
                    return video_url
                elif status == "error":
                    error_msg = status_data.get("error", {}).get("message", "Unknown error")
                    raise Exception(f"D-ID talk generation failed: {error_msg}")
                    
                print(f"⏳ Status: {status} (attempt {attempt + 1}/{max_retries})")
                
                # Use shorter delays for first few attempts
                if attempt < 5:
                    await asyncio.sleep(0.2)  # 200ms for first 5 attempts
                else:
                    await asyncio.sleep(delay)  # Then use configured delay
                    
            except Exception as e:
                print(f"❌ Error polling talk status: {e}")
                if attempt >= max_retries - 1:
                    raise
                    
        print(f"⏰ Timeout waiting for talk {talk_id}")
        return None
    
    async def wait_for_talk_completion_with_webhook(
        self, 
        did_talk_id: str,  # D-ID's talk ID for polling
        webhook_talk_id: str,  # Our talk ID for webhook
        max_retries: int = 30,
        delay: float = 0.5
    ) -> Optional[str]:
        """
        Wait for talk completion via webhook (fast) or polling (fallback)
        """
        print(f"⏳ Waiting for webhook ID {webhook_talk_id} (D-ID ID: {did_talk_id})...")
    
        # Import here to avoid circular imports
        from routes.webhooks import create_webhook_queue
        
    
        # Create queue using OUR webhook ID
        queue = create_webhook_queue(webhook_talk_id)
        print(f"📭 Queue created for {webhook_talk_id}")
    
        try:
            # Wait up to 15 seconds for webhook
            print(f"⏱️ Starting webhook wait at {time.time()}")
            result = await asyncio.wait_for(queue.get(), timeout=20.0)
            print(f"📬 Got webhook result at {time.time()}")
        
            if result.get("status") == "done":
                video_url = result.get("result_url")
                print(f"✅ Talk completed via webhook: {video_url}")
                return video_url
            elif result.get("status") == "error":
                error_msg = result.get("error", {}).get("message", "Unknown error")
                raise Exception(f"D-ID webhook error: {error_msg}")
            
        except asyncio.TimeoutError:
            print(f"⚠️ Webhook timeout at {time.time()}, falling back to polling...")
    
        # Fallback to polling using D-ID's talk ID
        return await self.wait_for_talk_completion(did_talk_id, max_retries, delay)

    
    def convert_pcm16_to_wav(self, pcm_chunks: List[str], sample_rate: int = 24000) -> str:
        """
        Convert PCM16 audio chunks to WAV format
        """
        pcm_data = b''
        for chunk in pcm_chunks:
            pcm_data += base64.b64decode(chunk)
        
        wav_buffer = io.BytesIO()
        
        channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        
        wav_buffer.write(b'RIFF')
        wav_buffer.write(struct.pack('<I', 36 + len(pcm_data)))
        wav_buffer.write(b'WAVE')
        
        wav_buffer.write(b'fmt ')
        wav_buffer.write(struct.pack('<I', 16))
        wav_buffer.write(struct.pack('<H', 1))
        wav_buffer.write(struct.pack('<H', channels))
        wav_buffer.write(struct.pack('<I', sample_rate))
        wav_buffer.write(struct.pack('<I', byte_rate))
        wav_buffer.write(struct.pack('<H', block_align))
        wav_buffer.write(struct.pack('<H', bits_per_sample))
        
        wav_buffer.write(b'data')
        wav_buffer.write(struct.pack('<I', len(pcm_data)))
        wav_buffer.write(pcm_data)
        
        wav_buffer.seek(0)
        wav_base64 = base64.b64encode(wav_buffer.read()).decode('utf-8')
        
        print(f"🎵 Converted {len(pcm_chunks)} PCM chunks to WAV ({len(wav_base64)} chars)")
        return wav_base64
    
    async def cleanup(self):
        """Clean up HTTP client"""
        await self.client.aclose()
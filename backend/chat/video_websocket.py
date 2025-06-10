"""
WebSocket handler for D-ID video streaming coordination
"""

from fastapi import WebSocket, WebSocketDisconnect
import json
import logging
from typing import Optional, Dict
import asyncio
from datetime import datetime

from video.processor import get_video_processor
import config.runtime_config as runtime_config

logger = logging.getLogger(__name__)


class VideoStreamManager:
    """Manages active video streams and WebSocket connections"""
    
    def __init__(self):
        self.active_streams: Dict[str, Dict] = {}  # user_uuid -> stream info
        self.websockets: Dict[str, WebSocket] = {}  # user_uuid -> websocket
        
    async def create_stream_for_user(self, user_uuid: str, websocket: WebSocket) -> Dict:
        """Create a D-ID stream for a user"""
        try:
            # Store websocket
            self.websockets[user_uuid] = websocket
            
            # Get video processor
            processor = get_video_processor()
            
            # Create stream
            source_url = runtime_config.get("DID_AVATAR_SOURCE_URL")
            if not source_url:
                raise ValueError("DID_AVATAR_SOURCE_URL not configured")
            stream_info = await processor.create_stream(source_url)
            
            # Store stream info
            self.active_streams[user_uuid] = {
                "stream_id": stream_info["id"],
                "session_id": stream_info["session_id"],
                "created_at": datetime.now(),
                "websocket": websocket
            }
            
            logger.info(f"✅ Created video stream for user {user_uuid}: {stream_info['id']}")
            
            return stream_info
            
        except Exception as e:
            logger.error(f"Failed to create stream for {user_uuid}: {e}")
            raise
            
    async def send_text_to_stream(self, user_uuid: str, text: str) -> None:
        """Send text to user's active stream"""
        stream_info = self.active_streams.get(user_uuid)
        if not stream_info:
            logger.warning(f"No active stream for user {user_uuid}")
            return
            
        try:
            processor = get_video_processor()
            
            # Track timing
            start_time = datetime.now()
            
            # Send text to D-ID
            result = await processor.create_talk(
                stream_info["stream_id"],
                stream_info["session_id"],
                {"text": text}
            )
            
            # Calculate latency
            latency = (datetime.now() - start_time).total_seconds()
            
            # Notify frontend
            if user_uuid in self.websockets:
                await self.websockets[user_uuid].send_json({
                    "type": "did_talk_generated",
                    "stream_id": stream_info["stream_id"],
                    "text": text[:50] + "..." if len(text) > 50 else text,
                    "latency": latency,
                    "timestamp": datetime.now().isoformat()
                })
                
            logger.info(f"✅ Sent text to stream {stream_info['stream_id']} (latency: {latency:.2f}s)")
            
        except Exception as e:
            logger.error(f"Failed to send text to stream: {e}")
            
            # Notify frontend of error
            if user_uuid in self.websockets:
                await self.websockets[user_uuid].send_json({
                    "type": "did_talk_error",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
                
    async def close_stream(self, user_uuid: str) -> None:
        """Close user's video stream"""
        stream_info = self.active_streams.get(user_uuid)
        if not stream_info:
            return
            
        try:
            processor = get_video_processor()
            await processor.close_stream(
                stream_info["stream_id"],
                stream_info["session_id"]
            )
            
            logger.info(f"✅ Closed stream {stream_info['stream_id']} for user {user_uuid}")
            
        except Exception as e:
            logger.error(f"Error closing stream: {e}")
            
        finally:
            # Clean up
            if user_uuid in self.active_streams:
                del self.active_streams[user_uuid]
            if user_uuid in self.websockets:
                del self.websockets[user_uuid]


# Global instance
video_stream_manager = VideoStreamManager()


async def video_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for video streaming coordination"""
    await websocket.accept()
    
    user_uuid = websocket.query_params.get("user_uuid", "")
    logger.info(f"🎬 Video WebSocket connected: {user_uuid}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            message_type = message.get("type")
            
            if message_type == "create_stream":
                # Create D-ID stream
                stream_info = await video_stream_manager.create_stream_for_user(
                    user_uuid, websocket
                )
                
                # Send stream info to frontend
                await websocket.send_json({
                    "type": "stream_created",
                    "stream_id": stream_info["id"],
                    "session_id": stream_info["session_id"],
                    "offer": stream_info["offer"],
                    "ice_servers": stream_info["ice_servers"]
                })
                
            elif message_type == "ice_candidate":
                # Forward ICE candidate to D-ID
                stream_info = video_stream_manager.active_streams.get(user_uuid)
                if stream_info:
                    processor = get_video_processor()
                    await processor.send_ice_candidate(
                        stream_info["stream_id"],
                        stream_info["session_id"],
                        message["candidate"]
                    )
                    
            elif message_type == "close_stream":
                await video_stream_manager.close_stream(user_uuid)
                
    except WebSocketDisconnect:
        logger.info(f"🔌 Video WebSocket disconnected: {user_uuid}")
    except Exception as e:
        logger.error(f"Video WebSocket error: {e}")
    finally:
        await video_stream_manager.close_stream(user_uuid)
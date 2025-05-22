"""
WebRTC Signaling for FastAPI
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import uuid
import json
import asyncio
from typing import Dict, Any, Optional, List

# Create router
router = APIRouter()

# Session storage
sessions = {}

# WebSocket connections
connections = {}

class WebRTCSession:
    def __init__(self, session_id: str, websocket: WebSocket):
        self.id = session_id
        self.websocket = websocket
        self.created_at = asyncio.get_event_loop().time()
        self.is_ready = False
        self.offers = []
        self.answers = []
        self.candidates = []
        
    async def send_message(self, message_type: str, data: Dict[str, Any]):
        await self.websocket.send_text(json.dumps({
            "type": message_type,
            "data": data
        }))

@router.websocket("/webrtc")
async def webrtc_endpoint(websocket: WebSocket):
    # Accept connection
    await websocket.accept()
    
    # Create session
    session_id = str(uuid.uuid4())
    session = WebRTCSession(session_id, websocket)
    sessions[session_id] = session
    connections[websocket] = session
    
    # Send session info
    await session.send_message("session", {
        "sessionId": session_id
    })
    
    try:
        # Process messages
        while True:
            data = await websocket.receive_text()
            await process_message(session, data)
    except WebSocketDisconnect:
        # Clean up
        if websocket in connections:
            session = connections[websocket]
            if session.id in sessions:
                del sessions[session.id]
            del connections[websocket]
        print(f"Client disconnected: {session_id}")

async def process_message(session: WebRTCSession, message: str):
    try:
        data = json.loads(message)
        message_type = data.get("type")
        message_data = data.get("data", {})
        
        print(f"Received {message_type} from client {session.id}")
        
        if message_type == "join":
            await handle_join(session, message_data)
        elif message_type == "offer":
            await handle_offer(session, message_data)
        elif message_type == "answer":
            await handle_answer(session, message_data)
        elif message_type == "candidate":
            await handle_candidate(session, message_data)
        else:
            print(f"Unknown message type: {message_type}")
    except json.JSONDecodeError:
        print(f"Invalid JSON message: {message}")
    except Exception as e:
        print(f"Error processing message: {e}")

async def handle_join(session: WebRTCSession, data: Dict[str, Any]):
    """Handle client join request"""
    session.is_ready = True
    
    # Tell client that we're ready
    await session.send_message("ready", {
        "sessionId": session.id,
        "capabilities": {
            "audio": True,
            "video": False
        }
    })

async def handle_offer(session: WebRTCSession, data: Dict[str, Any]):
    """Handle client WebRTC offer"""
    offer = data.get("offer")
    if not offer:
        return
    
    session.offers.append(offer)
    
    # In a real implementation, this would be sent to the assistant backend
    # For now, we'll just echo back a sample answer for testing
    await asyncio.sleep(0.5)
    
    # Send a pre-defined answer (this is just for testing - not a real connection)
    await session.send_message("answer", {
        "answer": {
            "type": "answer",
            "sdp": "v=0\r\no=- 123456789 123456789 IN IP4 0.0.0.0\r\ns=-\r\nt=0 0\r\na=group:BUNDLE 0\r\na=ice-options:trickle\r\na=msid-semantic:WMS *\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\nc=IN IP4 0.0.0.0\r\na=rtcp:9 IN IP4 0.0.0.0\r\na=ice-ufrag:fake\r\na=ice-pwd:fake\r\na=fingerprint:sha-256 00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00:00\r\na=setup:active\r\na=mid:0\r\na=sendrecv\r\na=rtcp-mux\r\na=rtpmap:111 opus/48000/2\r\na=fmtp:111 minptime=10;useinbandfec=1\r\n"
        }
    })
    
    # Send an ICE candidate (again, just for testing)
    await session.send_message("candidate", {
        "candidate": {
            "candidate": "candidate:0 1 UDP 2122252543 192.168.1.100 12345 typ host",
            "sdpMid": "0",
            "sdpMLineIndex": 0
        }
    })

async def handle_answer(session: WebRTCSession, data: Dict[str, Any]):
    """Handle client WebRTC answer"""
    answer = data.get("answer")
    if not answer:
        return
    
    session.answers.append(answer)
    print(f"Received answer from client {session.id}")

async def handle_candidate(session: WebRTCSession, data: Dict[str, Any]):
    """Handle client ICE candidate"""
    candidate = data.get("candidate")
    if not candidate:
        return
    
    session.candidates.append(candidate)
    print(f"Received ICE candidate from client {session.id}")
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio
import logging
import traceback
import httpx
import websocket
import threading
import queue
from typing import Optional
import sys

from config import OPENAI_API_KEY
from vector.rag import log_debug, retrieve_documents
from memory.persistent_memory import append_to_summary


logging.basicConfig(level=logging.DEBUG)
print("🖐️  LOADED /app/routes/realtime_chat.py")

websocket.enableTrace(True)

router = APIRouter()

async def execute_tool(name: str, args: dict, user_uuid: Optional[str]):
    """Handle tool execution server-side."""
    if name == "search_knowledge_base":
        query = args.get("query", "")
        print(f"🔍 DEBUG: Tool called with query: '{query}'")
        
        import time
        start_time = time.time()
        docs = await retrieve_documents(query)
        end_time = time.time()
        
        print(f"🔍 DEBUG: Retrieved {len(docs)} documents")
        if docs:
            print(f"🔍 DEBUG: First doc preview: {docs[0].get('text', '')[:100]}...")
        
        # Fix timing data format to match dashboard expectations
        timing_data = {
            "total": end_time - start_time,
            "retrieval": end_time - start_time,  # For realtime, retrieval = total
            "gpt": 0.0,  # No GPT call in tool execution
            "tool": name
        }
        
        if docs:
            formatted_docs = "\n\n---\n\n".join([f"Document {i+1}:\n{doc.get('text', '')}" for i, doc in enumerate(docs[:3])])
            answer_text = f"Found {len(docs)} relevant documents via realtime search.\n\n{formatted_docs}"
        else:
            answer_text = "Found 0 relevant documents via realtime search."
        
        log_debug(query, docs[:3], answer_text, timing_data)
        
        results = [
            {"content": d["text"], "source": d.get("source", ""), "relevance_score": d.get("score", 0)}
            for d in docs[:3]
        ]
        return {"results": results, "query": query, "total_results": len(docs)}
    elif name == "update_user_memory":
        uuid = args.get("user_uuid") or user_uuid
        if not isinstance(uuid, str) or not uuid:
            return {"error": "Missing or invalid user_uuid"}
        append_to_summary(uuid, args.get("information", ""))
        return {"success": True}
    return {"error": f"Unknown tool {name}"}

class OpenAIWebSocketClient:
    """WebSocket client using websocket-client library (official OpenAI example)"""
    
    def __init__(self, api_key: str, instructions: str = "", user_uuid: str = ""):
        self.api_key = api_key
        self.instructions = instructions
        self.user_uuid = user_uuid
        self.ws = None
        self.connected = False
        
        # Queues for communication between threads
        self.incoming_queue = queue.Queue()
        self.outgoing_queue = queue.Queue()
        
    def connect(self):
        """Connect to OpenAI using official websocket-client library"""
        url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"
        
        # Official format from OpenAI docs
        headers = [
            f"Authorization: Bearer {self.api_key}",
            "OpenAI-Beta: realtime=v1"
        ]
        
        print(f"🔗 Connecting to OpenAI: {url}")
        
        self.ws = websocket.WebSocketApp(
            url,
            header=headers,
            subprotocols=["realtime"],
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        
        # Run in separate thread
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()
        
        # Wait for connection
        import time
        for _ in range(50):  # Wait up to 5 seconds
            if self.connected:
                break
            time.sleep(0.1)
            
        return self.connected
    
    def on_open(self, ws):
        print("✅ Connected to OpenAI WebSocket")
        self.connected = True
        
        # Send session configuration (following the official docs)
        session_config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self.instructions or "You are a helpful AI assistant.",
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,           # TODO: Config Dashboard - Lower (0.3) = more sensitive
                    "prefix_padding_ms": 300,   # TODO: Config Dashboard - Higher (500) = less cutoff at start  
                    "silence_duration_ms": 200  # TODO: Config Dashboard - Higher (800-1000) = less interruption
                },
                "tools": [
                    {
                        "type": "function",
                        "name": "search_knowledge_base",
                        "description": "Search the Mobeus knowledge base for relevant information",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "The search query"
                                }
                            },
                            "required": ["query"]
                        }
                    },
                    {
                        "type": "function",
                        "name": "update_user_memory",
                        "description": "Store important information about the user",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "information": {
                                    "type": "string",
                                    "description": "Important information to remember"
                                },
                                "user_uuid": {
                                    "type": "string",
                                    "description": "The user's UUID"
                                }
                            },
                            "required": ["information", "user_uuid"]
                        }
                    }
                ]
            }
        }
        
        ws.send(json.dumps(session_config))
        print("📤 Sent session configuration")
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get('type', 'unknown')
            print(f"📤 OpenAI → Client: {msg_type}")
            
            # Handle function calls asynchronously
            if msg_type == "response.function_call_arguments.done":
                print(f"🔧 Function call: {data.get('name')}")
                # Create a new event loop thread for async function call
                import threading
                def handle_async_function_call():
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.handle_function_call(data))
                    loop.close()
                
                thread = threading.Thread(target=handle_async_function_call)
                thread.daemon = True
                thread.start()
            
            # Log important audio and conversation events
            elif msg_type in ['input_audio_buffer.speech_started', 'input_audio_buffer.speech_stopped', 
                            'conversation.item.created', 'response.audio.delta', 'response.audio.done',
                            'session.created', 'session.updated']:
                print(f"📤 OpenAI → Client: {msg_type} (important event)")
                if 'transcript' in data:
                    print(f"📝 Transcript: {data.get('transcript', '')}")
            
            # Put message in queue for forwarding to client
            self.incoming_queue.put(message)
            
        except Exception as e:
            print(f"❌ Error processing OpenAI message: {e}")
            traceback.print_exc()
    
    def on_error(self, ws, error):
        logger = logging.getLogger("realtime_chat")
        logger.setLevel(logging.INFO)
        logger.error("❌ WebSocket error", exc_info=error)
        print(f"❌ OpenAI WebSocket error: {error}")
        
    def on_close(self, ws, close_status_code, close_msg):
        logger = logging.getLogger("realtime_chat")
        logger.setLevel(logging.INFO)
        logging.getLogger("realtime_chat").info(f"🔒 OpenAI WebSocket closed (code={close_status_code}, reason={close_msg})")
        print(f"🔌 OpenAI WebSocket closed: {close_status_code} - {close_msg}")
        self.connected = False
    
    async def handle_function_call(self, event):
        """Handle function calls from OpenAI"""
        name = event.get("name")
        call_id = event.get("call_id") 
        args = {}
        if event.get("arguments"):
            try:
                args = json.loads(event["arguments"])
            except Exception:
                args = {}
        
        if not isinstance(name, str) or not name:
            result = {"error": "Missing or invalid function name"}
        else:
            result = await execute_tool(name, args, self.user_uuid)
        
        # Send function result back to OpenAI
        response_event = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(result),
            },
        }
        
        if self.ws and self.connected:
            self.ws.send(json.dumps(response_event))
            
            # Request new response
            create_response = {"type": "response.create", "response": {"modalities": ["text", "audio"]}}
            self.ws.send(json.dumps(create_response))
    
    def send_message(self, message):
        """Send message to OpenAI"""
        if self.ws and self.connected:
            self.ws.send(message)
            return True
        return False
    
    def get_message(self):
        """Get message from OpenAI (non-blocking)"""
        try:
            return self.incoming_queue.get_nowait()
        except queue.Empty:
            return None
    
    def close(self):
        """Close connection"""
        if self.ws:
            self.ws.close()
        self.connected = False

@router.websocket("/api/realtime/chat")
async def realtime_chat(websocket: WebSocket):
    # 1) Accept connection and prove we’re here
    await websocket.accept()
    print("🖐️  ACCEPTED websocket")
    logger = logging.getLogger("realtime_chat")
    logger.setLevel(logging.INFO)

    user_uuid = websocket.query_params.get("user_uuid", "")
    logger.info(f"➡️ Client connected: {user_uuid!r}")
    print(f"🎯 WebSocket client connected - UUID: {user_uuid!r}")

    # 2) Wrap *all* your logic in try/except
    openai_client = None
    try:
        # … your existing instruction‐enrichment code …
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be set")
        openai_client = OpenAIWebSocketClient(
            api_key=OPENAI_API_KEY,
        )
        if not openai_client.connect():
            raise RuntimeError("Failed to connect to OpenAI")

        # Tell the browser we’re ready
        await websocket.send_json({"type": "session.created", "session": {"status": "ready"}})
        print("✅ Session ready, client notified")

        # Spawn the two loops
        async def forward_from_openai():
            while openai_client.connected:
                msg = openai_client.get_message()
                if msg:
                    print(f"⬅️ OpenAI → backend event")
                    await websocket.send_text(msg)
                    print(f"📤 Forwarded event to browser")
                await asyncio.sleep(0.01)

        async def forward_from_client():
            while True:
                data = await websocket.receive_text()
                print(f"📥 Received from browser ({len(data)} bytes)")
                # … parse, log, and send to OpenAI …
                if not openai_client.send_message(data):
                    print("❌ Failed to send to OpenAI")
                    return

        # Run them together
        await asyncio.gather(
            forward_from_openai(),
            forward_from_client(),
        )

    except WebSocketDisconnect:
        print("🔌 Client disconnected")
    except Exception as e:
        # Catch anything else
        print("❌ Exception in realtime_chat handler:", e)
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except:
            pass

    finally:
        # Always clean up
        if openai_client:
            openai_client.close()
        print("🧹 Connection cleanup completed")
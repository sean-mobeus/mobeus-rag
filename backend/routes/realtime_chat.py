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
import runtime_config
import datetime

from config import OPENAI_API_KEY
from vector.rag import log_debug, retrieve_documents
from memory.persistent_memory import append_to_summary
from memory.session_memory import log_interaction, get_all_session_memory
from memory.persistent_memory import get_summary

logging.basicConfig(level=logging.DEBUG)
print("🖐️  LOADED /app/routes/realtime_chat.py")

# Disable low-level websocket-client trace logs to avoid audio data spam
# websocket.enableTrace(False)

router = APIRouter()

async def execute_tool(name: str, args: dict, user_uuid: Optional[str]):
    """Handle tool execution server-side."""
    if name == "search_knowledge_base":
        query = args.get("query", "")
        print(f"🔍 Tool called: search_knowledge_base with query: '{query}'")
        
        import time
        start_time = time.time()
        docs = await retrieve_documents(query)
        end_time = time.time()
        
        print(f"🔍 Retrieved {len(docs)} documents")
        if docs:
            print(f"🔍 First doc preview: {docs[0].get('text', '')[:100]}...")
        
        timing_data = {
            "total": end_time - start_time,
            "retrieval": end_time - start_time,
            "gpt": 0.0,
            "tool": name
        }
        
        if docs:
            formatted_docs = "\n\n---\n\n".join([f"Document {i+1}:\n{doc.get('text', '')}" for i, doc in enumerate(docs[:3])])
            answer_text = f"Found {len(docs)} relevant documents about Mobeus.\n\n{formatted_docs}"
        else:
            answer_text = "No relevant documents found in the Mobeus knowledge base."
        
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
    
    def __init__(self, api_key: str, user_uuid: str = ""):
        self.api_key = api_key
        self.user_uuid = user_uuid
        self.ws = None
        self.connected = False
        
        # Queues for communication between threads
        self.incoming_queue = queue.Queue()
        self.outgoing_queue = queue.Queue()
        
        # Track RAG injection to prevent duplicates
        self.last_rag_injection_id: Optional[str] = None
        
    def connect(self):
        """Connect to OpenAI using official websocket-client library"""
        url = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"
        
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
    
        # Get config values
        realtime_model = runtime_config.get("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
        realtime_voice = runtime_config.get("REALTIME_VOICE", "alloy")
        temperature = runtime_config.get("TEMPERATURE", 0.7)
        modalities = runtime_config.get("REALTIME_MODALITIES", ["text", "audio"])
        audio_format = runtime_config.get("REALTIME_AUDIO_FORMAT", "pcm16")
        turn_detection_type = runtime_config.get("TURN_DETECTION_TYPE", "server_vad")
        turn_detection_threshold = runtime_config.get("TURN_DETECTION_THRESHOLD", 0.5)
        turn_detection_silence_ms = runtime_config.get("TURN_DETECTION_SILENCE_MS", 200)
        tone_style = runtime_config.get("TONE_STYLE", "empathetic")
        
        # Build context for the assistant
        context_parts = []
        
        if self.user_uuid:
            # Get persistent memory (long-term user info)
            persistent_summary = get_summary(self.user_uuid)
            if persistent_summary:
                context_parts.append(f"User Background:\n{persistent_summary}")
            
            # Get recent session memory
            session_memory = get_all_session_memory(self.user_uuid)
            if session_memory:
                conversation_context = []
                for interaction in session_memory[-8:]:  # Last 8 interactions for context
                    role = interaction["role"].title()
                    message = interaction["message"]
                    conversation_context.append(f"{role}: {message}")
                
                if conversation_context:
                    context_parts.append("Recent Conversation:\n" + "\n".join(conversation_context))
        
        # Build base system instructions with tone style
        base_instructions = runtime_config.get("SYSTEM_PROMPT", "").format(tone_style=tone_style)

        # Add user context if available
        if context_parts:
            full_instructions = base_instructions + f"\n\nContext about this user:\n\n{chr(10).join(context_parts)}"
        else:
            full_instructions = base_instructions
        
        print(f"🎛️ System instructions length: {len(full_instructions)} characters")
        
        # Build complete session configuration, including user speech transcription
        session_config = {
            "type": "session.update",
            "session": {
                "model": realtime_model,
                "voice": realtime_voice,
                "modalities": modalities,
                "input_audio_format": audio_format,
                "output_audio_format": audio_format,
                "temperature": temperature,
                "instructions": full_instructions,
                # Enable user audio transcription via Whisper
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection": {
                    "type": turn_detection_type,
                    "threshold": turn_detection_threshold,
                    "silence_duration_ms": turn_detection_silence_ms,
                    "prefix_padding_ms": 300
                },
                "tools": [
                    {
                        "type": "function",
                        "name": "search_knowledge_base",
                        "description": "Search the Mobeus knowledge base for specific information about Mobeus products, services, features, or company details",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {
                                    "type": "string",
                                    "description": "Search query to find relevant Mobeus information"
                                }
                            },
                            "required": ["query"]
                        }
                    },
                    {
                        "type": "function", 
                        "name": "update_user_memory",
                        "description": "Store important information about the user for future conversations",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "information": {
                                    "type": "string",
                                    "description": "Important information to remember about the user (name, goals, preferences, etc.)"
                                }
                            },
                            "required": ["information"]
                        }
                    }
                ]
            }
        }
        
        # Send configuration to OpenAI
        ws.send(json.dumps(session_config))
        print(f"📤 Sent session config: model={realtime_model}, voice={realtime_voice}, temp={temperature}, tone={tone_style}")
        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get('type', 'unknown')
            
            # FIXED: Improved conversation logging with correct event structures
            if self.user_uuid:
                if msg_type == "conversation.item.input_audio_transcription.completed":
                    # User audio transcription completed - this is the reliable way to get user speech
                    transcript = data.get("transcript", "").strip()
                    if transcript:
                        print(f"💬 Logging user audio: {transcript[:100]}...")
                        log_interaction(self.user_uuid, "user", transcript)
                
                elif msg_type == "conversation.item.created":
                    item = data.get("item", {})
                    if item.get("type") == "message":
                        role = item.get("role")
                        if role == "user":
                            # Extract user text content (for text input, not audio)
                            content = ""
                            if item.get("content"):
                                for content_part in item["content"]:
                                    if content_part.get("type") in ("input_text", "text"): 
                                        content = content_part.get("text", "")
                                        break
                            
                            if content:
                                print(f"💬 Logging user text: {content[:100]}...")
                                log_interaction(self.user_uuid, "user", content)
                        
                        elif role == "assistant":
                            # Extract assistant content 
                            content = ""
                            if item.get("content"):
                                for content_part in item["content"]:
                                    if content_part.get("type") == "text":
                                        content += content_part.get("text", "")
                            
                            if content:
                                print(f"💬 Logging assistant message: {content[:100]}...")
                                log_interaction(self.user_uuid, "assistant", content)
                
                elif msg_type == "response.audio_transcript.done":
                    # Complete transcript of what AI said (more reliable than response.done)
                    transcript = data.get("transcript", "").strip()
                    if transcript:
                        print(f"💬 Logging assistant audio transcript: {transcript[:100]}...")
                        log_interaction(self.user_uuid, "assistant", transcript)
            
            # Handle function calls
            if msg_type == "response.function_call_arguments.done":
                print(f"🔧 Function call: {data.get('name')}")
                def handle_async_function_call():
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.handle_function_call(data))
                    loop.close()
                
                thread = threading.Thread(target=handle_async_function_call)
                thread.daemon = True
                thread.start()
            
            # Put message in queue for forwarding to client
            self.incoming_queue.put(message)
            
        except Exception as e:
            print(f"❌ Error processing OpenAI message: {e}")
            traceback.print_exc()
    
    def on_error(self, ws, error):
        print(f"❌ OpenAI WebSocket error: {error}")
        
    def on_close(self, ws, close_status_code, close_msg):
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
    await websocket.accept()
    print("🖐️  ACCEPTED websocket")
    
    user_uuid = websocket.query_params.get("user_uuid", "")
    print(f"🎯 WebSocket client connected - UUID: {user_uuid!r}")

    openai_client = None
    try:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be set")
            
        # Create client with user UUID for memory integration
        openai_client = OpenAIWebSocketClient(
            api_key=OPENAI_API_KEY,
            user_uuid=user_uuid
        )
        
        if not openai_client.connect():
            raise RuntimeError("Failed to connect to OpenAI")

        # Tell the browser we're ready
        await websocket.send_json({"type": "session.created", "session": {"status": "ready"}})
        print("✅ Session ready, Mobeus is online!")

        # FIXED: Simplified forwarding to prevent double RAG injection
        async def forward_from_openai():
            """Simply relay events from OpenAI to client without RAG injection"""
            while openai_client.connected:
                msg = openai_client.get_message()
                if msg:
                    await websocket.send_text(msg)
                await asyncio.sleep(0.01)

        async def forward_from_client():
            """Handle incoming client messages and inject RAG context ONCE ONLY"""
            while True:
                data = await websocket.receive_text()
                
                # FIXED: Only inject RAG context on specific client-sent messages
                try:
                    msg = json.loads(data)
                    if msg.get("type") == "conversation.item.create":
                        item = msg.get("item", {})
                        if item.get("type") == "message" and item.get("role") == "user":
                            # Extract user text content
                            user_text = ""
                            for part in item.get("content", []):
                                if part.get("type") in ("text", "input_text"):
                                    user_text = part.get("text", "")
                                    break
                            
                            if user_text:
                                print(f"🖐️ User text message: {user_text[:100]}")
                                
                                # Generate unique ID to prevent duplicate RAG injection
                                import hashlib
                                message_id = hashlib.md5(f"{user_text}{len(user_text)}".encode()).hexdigest()
                                
                                if message_id != openai_client.last_rag_injection_id:
                                    openai_client.last_rag_injection_id = message_id
                                    
                                    try:
                                        docs = await retrieve_documents(user_text)
                                        print(f"🔍 Retrieved {len(docs)} docs for user query")
                                        
                                        if docs:
                                            docs_text = "\n\n---\n\n".join([d.get("text", "") for d in docs[:3]])
                                            # Inject as system message with correct content type
                                            sys_event = {
                                                "type": "conversation.item.create",
                                                "item": {
                                                    "type": "message",
                                                    "role": "system",
                                                    "content": [{"type": "input_text", "text": f"Relevant Information from Mobeus knowledge base:\n{docs_text}"}]
                                                }
                                            }
                                            sys_msg = json.dumps(sys_event)
                                            print(f"📤 Injecting RAG info: {sys_msg[:200]}...")
                                            openai_client.send_message(sys_msg)
                                    except Exception as e:
                                        print(f"❌ Error retrieving documents: {e}")
                                else:
                                    print("⚠️ Skipping duplicate RAG injection")
                    
                    # Also handle audio transcription completion for RAG
                    elif msg.get("type") == "input_audio_buffer.commit":
                        # This indicates user finished speaking - transcript will come later
                        print("🎤 User finished speaking, awaiting transcript...")
                
                except Exception as e:
                    print(f"❌ Error processing client message: {e}")
                
                # Forward original client message to OpenAI
                if not openai_client.send_message(data):
                    print("❌ Failed to send to OpenAI")
                    return

        # Run both forwarding loops
        await asyncio.gather(
            forward_from_openai(),
            forward_from_client(),
        )

    except WebSocketDisconnect:
        print("🔌 Client disconnected")
    except Exception as e:
        print("❌ Exception in realtime_chat handler:", e)
        traceback.print_exc()
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except:
            pass

    finally:
        if openai_client:
            openai_client.close()
        print("🧹 Connection cleanup completed")

def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    """Estimate the cost of a request based on token usage and model."""
    # Updated pricing (per 1K tokens) - closer to actual OpenAI rates
    pricing = {
        "gpt-4o-realtime-preview-2024-12-17": {"input": 0.005, "output": 0.020},  # Realtime pricing
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4": {"input": 0.030, "output": 0.060},
        "default": {"input": 0.005, "output": 0.015}
    }
    price = pricing.get(model, pricing["default"])
    return (input_tokens / 1000) * price["input"] + (output_tokens / 1000) * price["output"]

def log_token_usage(user_uuid: str, input_tokens: int, output_tokens: int, model: str):
    """Log token usage for cost tracking"""
    with open("token_usage.jsonl", "a") as f:
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "user_uuid": user_uuid,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "model": model,
            "estimated_cost": calculate_cost(input_tokens, output_tokens, model)
        }
        f.write(json.dumps(entry) + "\n")
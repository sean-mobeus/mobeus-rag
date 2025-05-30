from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json
import asyncio
import logging
import traceback
import httpx
import websocket
import threading
import queue
from typing import Optional, Dict, Set
import os
import runtime_config
import datetime

from config import OPENAI_API_KEY
from vector.rag import log_debug, retrieve_documents
from memory.persistent_memory import append_to_summary
from memory.session_memory import log_interaction, get_all_session_memory
from memory.persistent_memory import get_summary
from stats.tools_dashboard import log_strategy_change, TOOL_STRATEGIES
from config import LOG_DIR


logging.basicConfig(level=logging.DEBUG)
print("🖐️  LOADED /app/routes/realtime_chat.py")

# Disable low-level websocket-client trace logs to avoid audio data spam
# websocket.enableTrace(False)

router = APIRouter()

# Real-time Session Manager for Strategy Broadcasting
class SessionManager:
    """Manages active voice sessions and broadcasts strategy updates"""
    
    def __init__(self):
        # Track active voice sessions
        self.voice_sessions: Dict[str, WebSocket] = {}  # user_uuid -> websocket
        self.dashboard_sessions: Set[WebSocket] = set()  # dashboard connections
        self.session_strategies: Dict[str, str] = {}  # user_uuid -> current strategy
        
    async def add_voice_session(self, user_uuid: str, websocket: WebSocket, initial_strategy: str = "auto"):
        """Add a voice session to the manager"""
        self.voice_sessions[user_uuid] = websocket
        self.session_strategies[user_uuid] = initial_strategy
        
        # Notify dashboards of new session
        await self.broadcast_to_dashboards({
            "type": "session_connected",
            "user_uuid": user_uuid,
            "strategy": initial_strategy,
            "total_sessions": len(self.voice_sessions)
        })
        
        print(f"✅ Voice session added: {user_uuid} (strategy: {initial_strategy})")
        
    async def remove_voice_session(self, user_uuid: str):
        """Remove a voice session from the manager"""
        if user_uuid in self.voice_sessions:
            del self.voice_sessions[user_uuid]
        if user_uuid in self.session_strategies:
            del self.session_strategies[user_uuid]
            
        # Notify dashboards of disconnection
        await self.broadcast_to_dashboards({
            "type": "session_disconnected", 
            "user_uuid": user_uuid,
            "total_sessions": len(self.voice_sessions)
        })
        
        print(f"🔌 Voice session removed: {user_uuid}")
        
    async def add_dashboard_session(self, websocket: WebSocket):
        """Add a dashboard session to the manager"""
        self.dashboard_sessions.add(websocket)
        
        # Send current session status to new dashboard
        await websocket.send_json({
            "type": "session_status",
            "active_sessions": [
                {"user_uuid": uuid, "strategy": strategy} 
                for uuid, strategy in self.session_strategies.items()
            ],
            "total_sessions": len(self.voice_sessions)
        })
        
        print(f"📊 Dashboard session added (total: {len(self.dashboard_sessions)})")
        
    async def remove_dashboard_session(self, websocket: WebSocket):
        """Remove a dashboard session from the manager"""
        self.dashboard_sessions.discard(websocket)
        print(f"📊 Dashboard session removed (total: {len(self.dashboard_sessions)})")
        
    async def broadcast_strategy_update(self, new_strategy: str, source_dashboard: Optional[WebSocket] = None):
        """Broadcast strategy update to ALL active voice sessions"""
        updates_sent = 0
        failed_sessions = []
        
        # Update all voice sessions
        for user_uuid, voice_websocket in self.voice_sessions.items():
            try:
                # Update our tracking
                old_strategy = self.session_strategies.get(user_uuid, "auto")
                self.session_strategies[user_uuid] = new_strategy
                
                # Send strategy update to voice session
                await voice_websocket.send_json({
                    "type": "strategy_update_broadcast",
                    "strategy": new_strategy,
                    "previous_strategy": old_strategy,
                    "source": "dashboard_broadcast"
                })
                
                updates_sent += 1
                print(f"🎛️ Strategy broadcast sent to {user_uuid}: {old_strategy} → {new_strategy}")
                
            except Exception as e:
                print(f"❌ Failed to send strategy update to {user_uuid}: {e}")
                failed_sessions.append(user_uuid)
        
        # Clean up failed sessions
        for user_uuid in failed_sessions:
            await self.remove_voice_session(user_uuid)
        
        # Notify all dashboards about the strategy change
        await self.broadcast_to_dashboards({
            "type": "strategy_broadcast_completed",
            "new_strategy": new_strategy,
            "sessions_updated": updates_sent,
            "total_sessions": len(self.voice_sessions)
        }, exclude=source_dashboard)
        
        print(f"✅ Strategy broadcast completed: {updates_sent} sessions updated to '{new_strategy}'")
        return updates_sent
        
    async def broadcast_to_dashboards(self, message: dict, exclude: Optional[WebSocket] = None):
        """Send message to all connected dashboards"""
        failed_dashboards = []
        
        for dashboard_ws in self.dashboard_sessions:
            if dashboard_ws == exclude:
                continue
                
            try:
                await dashboard_ws.send_json(message)
            except Exception as e:
                print(f"❌ Failed to send to dashboard: {e}")
                failed_dashboards.append(dashboard_ws)
        
        # Clean up failed dashboards
        for dashboard_ws in failed_dashboards:
            await self.remove_dashboard_session(dashboard_ws)
            
    def get_session_status(self):
        """Get current session status for debugging"""
        return {
            "voice_sessions": len(self.voice_sessions),
            "dashboard_sessions": len(self.dashboard_sessions),
            "session_strategies": self.session_strategies
        }

# Global session manager instance
session_manager = SessionManager()

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
    """WebSocket client with tool strategy control"""
    
    def __init__(self, api_key: str, user_uuid: str = "", initial_strategy: str = "auto"):
        self.api_key = api_key
        self.user_uuid = user_uuid
        self.ws = None
        self.connected = False
        
        # Strategy management
        self.current_strategy = initial_strategy
        self.strategy_history = []
        
        # Queues for communication between threads
        self.incoming_queue = queue.Queue()
        self.outgoing_queue = queue.Queue()
        
        # Track RAG injection to prevent duplicates
        self.last_rag_injection_id: Optional[str] = None
        
    def update_strategy(self, new_strategy: str) -> bool:
        """Update the tool calling strategy dynamically."""
        if new_strategy not in TOOL_STRATEGIES:
            print(f"❌ Invalid strategy: {new_strategy}")
            return False
            
        old_strategy = self.current_strategy
        self.current_strategy = new_strategy
        
        # Log the strategy change
        log_strategy_change(self.user_uuid, old_strategy, new_strategy)
        self.strategy_history.append({
            "timestamp": datetime.datetime.now().isoformat(),
            "old_strategy": old_strategy,
            "new_strategy": new_strategy
        })
        
        # Send session update to OpenAI with new tool_choice
        tool_choice = self.get_tool_choice_for_strategy(new_strategy)
        session_update = {
            "type": "session.update",
            "session": {
                "tool_choice": tool_choice
            }
        }
        
        if self.ws and self.connected:
            self.ws.send(json.dumps(session_update))
            print(f"🎛️ Strategy updated: {old_strategy} → {new_strategy} (tool_choice: {tool_choice})")
            return True
        else:
            print("⚠️ Cannot update strategy - not connected to OpenAI")
            return False
    
    def get_tool_choice_for_strategy(self, strategy: str) -> str:
        """Convert strategy to OpenAI tool_choice parameter."""
        strategy_mapping = {
            "auto": "auto",           # Let OpenAI decide
            "conservative": "auto",   # Auto but with conservative instructions
            "aggressive": "auto",     # Auto but with aggressive instructions  
            "none": "none",          # Never use tools
            "required": "required"   # Always use a tool
        }
        return strategy_mapping.get(strategy, "auto")
    
    def get_enhanced_instructions(self, base_instructions: str, strategy: str) -> str:
        """Add strategy-specific instructions to the base prompt."""
        strategy_instructions = {
            "conservative": """

TOOL USAGE STRATEGY: Conservative
• Respond directly to greetings, casual conversation, and general questions
• Only use tools when specifically asked about Mobeus products/services
• Prioritize natural conversation flow over tool usage
• Use tools sparingly and only when necessary for accuracy
""",
            "aggressive": """

TOOL USAGE STRATEGY: Aggressive  
• Proactively search knowledge base for any Mobeus-related content
• Store any personal information users mention
• When uncertain, always search first rather than guessing
• Prioritize accuracy and comprehensiveness over response speed
• Use tools frequently to provide detailed, well-researched answers
""",
            "none": """

TOOL USAGE STRATEGY: Direct Response Only
• Do not use any tools - respond directly to all queries
• Use your existing knowledge to answer questions
• Acknowledge when you might not have complete information
• Focus on natural, conversational responses
""",
            "required": """

TOOL USAGE STRATEGY: Always Use Tools
• Always search knowledge base before responding to questions
• Always store any user information mentioned
• Provide comprehensive, tool-enhanced responses
• Never respond without first using available tools
""",
            "auto": """

TOOL USAGE STRATEGY: Balanced
• Use tools intelligently based on context
• Search for Mobeus-specific information when needed
• Store important user details when mentioned
• Balance natural conversation with accurate information
"""
        }
        
        strategy_text = strategy_instructions.get(strategy, strategy_instructions["auto"])
        return base_instructions + strategy_text
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

    # Update the on_open method to use strategy-enhanced instructions
    def on_open(self, ws):
        print("✅ Connected to OpenAI WebSocket")
        self.connected = True
    
        # Get config values with strategy consideration
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
            # Get persistent memory
            persistent_summary = get_summary(self.user_uuid)
            if persistent_summary:
                context_parts.append(f"User Background:\n{persistent_summary}")
            
            # Get recent session memory
            session_memory = get_all_session_memory(self.user_uuid)
            if session_memory:
                conversation_context = []
                total_chars = 0
                session_limit = runtime_config.get("SESSION_MEMORY_CHAR_LIMIT", 15000)

                for interaction in reversed(session_memory):
                    role = interaction["role"].title()
                    message = interaction["message"]
                    interaction_text = f"{role}: {message}"

                    if total_chars + len(interaction_text) <= session_limit:
                        conversation_context.insert(0, interaction_text)
                        total_chars += len(interaction_text)
                    else:
                        break

                if conversation_context:
                    context_parts.append("Recent Conversation:\n" + "\n".join(conversation_context))
        
        # Build base system instructions with tone and strategy
        base_instructions = runtime_config.get("SYSTEM_PROMPT", "").format(tone_style=tone_style)
        
        # Add strategy-specific instructions
        enhanced_instructions = self.get_enhanced_instructions(base_instructions, self.current_strategy)

        # Add user context if available
        if context_parts:
            full_instructions = enhanced_instructions + f"\n\nContext about this user:\n\n{chr(10).join(context_parts)}"
        else:
            full_instructions = enhanced_instructions
        # Log the actual prompt being sent to OpenAI for dashboard analysis
        try:
            from config import LOG_DIR
            prompts_log_path = os.path.join(LOG_DIR, "actual_prompts.jsonl")
    
            with open(prompts_log_path, "a") as f:
                prompt_entry = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "user_uuid": self.user_uuid,
                    "final_prompt": full_instructions,
                    "prompt_length": len(full_instructions),
                    "estimated_tokens": len(full_instructions) // 4,  # Rough estimate
                    "strategy": self.current_strategy,
                    "model": realtime_model
                }
                f.write(json.dumps(prompt_entry) + "\n")
        except Exception as e:
            print(f"⚠️ Failed to log actual prompt: {e}")

        # Get tool_choice based on current strategy
        tool_choice = self.get_tool_choice_for_strategy(self.current_strategy)
        
        # Build complete session configuration
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
                "tool_choice": tool_choice,  # Apply strategy-based tool choice
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
        print(f"📤 Session config sent: model={realtime_model}, strategy={self.current_strategy}, tool_choice={tool_choice}")

        
    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get('type', 'unknown')
            
            #conversation logging with correct event structures
            if self.user_uuid:
                if msg_type == "conversation.item.input_audio_transcription.completed":
                    # User audio transcription completed - this is the reliable way to get user speech
                    transcript = data.get("transcript", "").strip()
                    if transcript:
                        print(f"💬 Logging user audio: {transcript[:100]}...")
                        log_interaction(self.user_uuid, "user", transcript) #This triggers auto-summarization
                
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
            import time
            execution_time = 0.1  # We don't track timing yet, use placeholder
            success = "error" not in result
            # Write to function log file
            function_log_path = os.path.join(LOG_DIR, "function_calls.jsonl")
            with open(function_log_path, "a") as f:
                entry = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "function_name": name,
                    "arguments": args,
                    "result": result,
                    "execution_time": execution_time,
                    "success": success,
                    "strategy": self.current_strategy,
                    "user_uuid": self.user_uuid
                }
                f.write(json.dumps(entry) + "\n")
        
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

def detect_summary_request(message_text: str) -> bool:
    """Detect if user is requesting a conversation summary"""
    summary_triggers = [
        "summarize our conversation",
        "summarize what we discussed", 
        "give me a summary",
        "summarize this conversation",
        "create a summary",
        "can you summarize",
        "summarize what we talked about",
        "sum up our chat",
        "recap our conversation"
    ]
    
    message_lower = message_text.lower().strip()
    return any(trigger in message_lower for trigger in summary_triggers)

@router.websocket("/api/realtime/chat")
async def realtime_chat(websocket: WebSocket):
    await websocket.accept()
    print("🖐️  ACCEPTED websocket")
    
    user_uuid = websocket.query_params.get("user_uuid", "")
    initial_strategy = websocket.query_params.get("tool_strategy", "auto")
    print(f"🎯 WebSocket client connected - UUID: {user_uuid!r}, Strategy: {initial_strategy}")
    await session_manager.add_voice_session(user_uuid, websocket, initial_strategy)

    openai_client = None
    try:
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY must be set")
            
        # Create client with user UUID for memory integration and strategy support
        openai_client = OpenAIWebSocketClient(
            api_key=OPENAI_API_KEY,
            user_uuid=user_uuid,
            initial_strategy=initial_strategy
        )
        
        if not openai_client.connect():
            raise RuntimeError("Failed to connect to OpenAI")

        # Tell the browser we're ready with current strategy
        await websocket.send_json({
            "type": "session.created", 
            "session": {
                "status": "ready",
                "strategy": initial_strategy
            }
        })
        print("✅ Session ready, Mobeus is online!")

        # Simplified forwarding to prevent double RAG injection
        async def forward_from_openai():
            """Simply relay events from OpenAI to client without RAG injection"""
            while openai_client.connected:
                msg = openai_client.get_message()
                if msg:
                    await websocket.send_text(msg)
                await asyncio.sleep(0.01)

        async def forward_from_client():
            """Handle incoming client messages including strategy updates and RAG injection"""
            while True:
                data = await websocket.receive_text()
                
                # Only inject RAG context on specific client-sent messages
                try:
                    msg = json.loads(data)
                    msg_type = msg.get("type")

                    # Handle strategy updates (from dashboard broadcast OR direct client)
                    if msg_type in ["strategy_update", "strategy_update_broadcast"]:
                        new_strategy = msg.get("strategy", "auto")
                        print(f"🎛️ Received strategy update: {new_strategy}")

                        if openai_client.update_strategy(new_strategy):
                            # Update session manager tracking
                            session_manager.session_strategies[user_uuid] = new_strategy

                            # Confirm strategy update to client
                            await websocket.send_json({
                                "type": "session.updated",
                                "strategy": new_strategy,
                                "previous_strategy": openai_client.strategy_history[-1]["old_strategy"] if openai_client.strategy_history else "unknown",
                                "timestamp": datetime.datetime.now().isoformat(),
                                "source": msg.get("source", "direct")                                
                            })
                            print(f"✅ Strategy update confirmed: {new_strategy}")
                        else:
                            # Send error response
                            await websocket.send_json({
                                "type": "error",
                                "error": f"Failed to update strategy to {new_strategy}"
                            })
                        continue

                    # Handle RAG injection for user messages
                    elif msg_type == "conversation.item.create":
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
                            
                                # CHECK FOR SUMMARY REQUEST FIRST
                                if detect_summary_request(user_text):
                                    print(f"🎯 SUMMARY REQUEST DETECTED from {user_uuid}")
                                
                                    # Import here to avoid circular imports
                                    from memory.session_memory import force_session_summary
                                
                                    # Force the summary
                                    success = force_session_summary(user_uuid, "user_requested_mid_session")
                                
                                    if success:
                                        # Send confirmation back to user via OpenAI assistant
                                        confirmation_message = "I've created a summary of our conversation and stored it in your persistent memory."
                                    
                                        # Create a system message to make the assistant respond with confirmation
                                        system_response = {
                                            "type": "conversation.item.create",
                                            "item": {
                                                "type": "message",
                                                "role": "system",
                                                "content": [{"type": "input_text", "text": f"Respond to the user with this exact message: '{confirmation_message}'"}]
                                            }
                                        }
                                        openai_client.send_message(json.dumps(system_response))
                                        print(f"✅ User-triggered summary completed for {user_uuid}")
                                    
                                        # Skip the rest of processing for this message
                                        continue
                                    else:
                                        # Send error message
                                        error_message = "I wasn't able to create a summary right now. There might not be enough conversation content yet."
                                        error_response = {
                                            "type": "conversation.item.create",
                                            "item": {
                                                "type": "message",
                                                "role": "system",
                                                "content": [{"type": "input_text", "text": f"Respond to the user with this exact message: '{error_message}'"}]
                                            }
                                        }
                                        openai_client.send_message(json.dumps(error_response))
                                        continue
                                
                                # Only inject RAG if strategy allows it
                                if openai_client.current_strategy != "none":
                                    import hashlib
                                    message_id = hashlib.md5(f"{user_text}{len(user_text)}".encode()).hexdigest()
                                
                                    if message_id != openai_client.last_rag_injection_id:
                                        openai_client.last_rag_injection_id = message_id
                                    
                                        try:
                                            docs = await retrieve_documents(user_text)
                                            print(f"🔍 Retrieved {len(docs)} docs for user query (strategy: {openai_client.current_strategy})")
                                        
                                            if docs:
                                                docs_text = "\n\n---\n\n".join([d.get("text", "") for d in docs[:3]])
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
                                else:
                                    print(f"⏭️ Skipping RAG injection (strategy: {openai_client.current_strategy})")

                except Exception as e:
                    print(f"❌ Error processing client message: {e}")
                        
                # Forward original client message to OpenAI )unless it's a strategy update)
                try:
                    parsed_msg = json.loads(data)
                    if parsed_msg.get("type") not in ["strategy_update", "strategy_update_broadcast"]:
                        if not openai_client.send_message(data):
                            print("❌ Failed to send to OpenAI")
                            return
                except:
                    # If not valid JSON, forward as-is
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
        try:
            await websocket.send_json({"type": "error", "error": str(e)})
        except:
            pass

    finally:
        # Remove from session manager
        await session_manager.remove_voice_session(user_uuid)
        print(f"🧹 CLEANUP STARTED: user_uuid={user_uuid}")

        # FORCE auto-summarization on disconnect
        if user_uuid and user_uuid.strip():
            from memory.session_memory import force_session_summary
            force_session_summary(user_uuid, "auto_disconnect")
        else:
            print("⚠️ CLEANUP: No valid user_uuid for summarization")
    
    # Close OpenAI client
    if openai_client:
        try:
            openai_client.close()
            print("🔌 OpenAI client closed successfully")
        except Exception as e:
            print(f"⚠️ Error closing OpenAI client: {e}")
    
    print("🧹 CLEANUP COMPLETED")

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


# Add dashboard WebSocket endpoint for real-time strategy control
@router.websocket("/api/admin/dashboard")
async def dashboard_websocket(websocket: WebSocket):
    """WebSocket endpoint for dashboard real-time communication"""
    await websocket.accept()
    
    try:
        # Add to session manager
        await session_manager.add_dashboard_session(websocket)
        
        print("📊 Dashboard WebSocket connected")
        
        # Handle messages from dashboard
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type")
                
                if message_type == "broadcast_strategy_update":
                    # Dashboard wants to update strategy for all sessions
                    new_strategy = message.get("strategy", "auto")
                    print(f"📡 Dashboard requesting strategy broadcast: {new_strategy}")
                    
                    # Broadcast to all voice sessions
                    updates_sent = await session_manager.broadcast_strategy_update(
                        new_strategy, 
                        source_dashboard=websocket
                    )
                    
                    # Confirm to requesting dashboard
                    await websocket.send_json({
                        "type": "broadcast_confirmed",
                        "strategy": new_strategy,
                        "sessions_updated": updates_sent
                    })
                    
                elif message_type == "get_session_status":
                    # Dashboard requesting current status
                    status = session_manager.get_session_status()
                    await websocket.send_json({
                        "type": "session_status_response",
                        **status
                    })
                    
                else:
                    print(f"🤷 Unknown dashboard message type: {message_type}")
                    
            except json.JSONDecodeError:
                print(f"❌ Invalid JSON from dashboard: {data}")
            except Exception as e:
                print(f"❌ Error processing dashboard message: {e}")
                
    except Exception as e:
        print(f"❌ Dashboard WebSocket error: {e}")
    finally:
        await session_manager.remove_dashboard_session(websocket)
        print("🔌 Dashboard WebSocket disconnected")


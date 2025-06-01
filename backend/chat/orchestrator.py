from fastapi import WebSocket, WebSocketDisconnect
import json
import asyncio
import logging
import traceback
from typing import Optional, Dict, Set
import os
import datetime

from config import OPENAI_API_KEY
import config.runtime_config as runtime_config
from rag.retriever import log_debug, retrieve_documents
from memory.client import MemoryClient
from stats.collector import log_strategy_change
from stats.tools_dashboard import TOOL_STRATEGIES
from chat.realtime_client import OpenAIWebSocketClient
from voice_commands.commands import handle_summary_request


logging.basicConfig(level=logging.DEBUG)
print("🖐️  LOADED /app/routes/realtime_chat.py")

memory_client = MemoryClient()

# Disable low-level websocket-client trace logs to avoid audio data spam
# websocket.enableTrace(False)


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
        memory_client.append_summary(uuid, args.get("information", ""))
        return {"success": True}
        
    return {"error": f"Unknown tool {name}"}

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
                try:
                    data = await websocket.receive_text()
                except WebSocketDisconnect:
                    print("🔌 Client disconnected from forward_from_client")
                    break
                except Exception as e:
                    print(f"❌ Error receiving from client: {e}")
                    break
                
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
                            
                                # Handle voice command for mid-session summary
                                if handle_summary_request(
                                    user_text,
                                    memory_client,
                                    user_uuid,
                                    send_json=lambda msg: openai_client.send_message(json.dumps(msg)),
                                    modalities=runtime_config.get("REALTIME_MODALITIES", ["text", "audio"]),
                                ):
                                    continue

                                # Only inject RAG if strategy allows it
                                if openai_client.current_strategy != "none":
                                    import hashlib
                                    message_id = hashlib.md5(f"{user_text}{len(user_text)}".encode()).hexdigest()

                                    if message_id != openai_client.last_rag_injection_id:
                                        openai_client.last_rag_injection_id = message_id

                                        try:
                                            # Retrieve configured number of top documents
                                            top_k = runtime_config.get("RAG_RESULT_COUNT")
                                            docs = await retrieve_documents(user_text, top_k)
                                            print(f"🔍 Retrieved {len(docs)} docs for user query (strategy: {openai_client.current_strategy})")

                                            if docs:
                                                docs_text = "\n\n---\n\n".join(d.get("text", "") for d in docs)
                                                sys_event = {
                                                    "type": "conversation.item.create",
                                                    "item": {
                                                        "type": "message",
                                                        "role": "system",
                                                        "content": [
                                                            {
                                                                "type": "input_text",
                                                                "text": f"Relevant Information from Mobeus knowledge base:\n{docs_text}"
                                                            }
                                                        ]
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
                        
                # Forward original client message to OpenAI (unless it's a strategy update)
                try:
                    parsed_msg = json.loads(data)
                    if parsed_msg.get("type") not in ["strategy_update", "strategy_update_broadcast"]:
                        # Normalize legacy 'text' content type to 'input_text' for compatibility
                        if parsed_msg.get("type") == "conversation.item.create":
                            item = parsed_msg.get("item", {})
                            if item.get("type") == "message":
                                for part in item.get("content", []):
                                    if part.get("type") == "text":
                                        part["type"] = "input_text"
                        updated_data = json.dumps(parsed_msg)
                        if not openai_client.send_message(updated_data):
                            print("❌ Failed to send to OpenAI")
                            return
                except:
                    # If not valid JSON or normalization fails, forward as-is
                    if not openai_client.send_message(data):
                        print("❌ Failed to send to OpenAI")
                        return
                    
        # Run both forwarding loops
        await asyncio.gather(
            forward_from_openai(),
            forward_from_client(),
        )

    finally:
        # Remove from session manager
        await session_manager.remove_voice_session(user_uuid)
        print(f"🧹 CLEANUP STARTED: user_uuid={user_uuid}")

        # FORCE auto-summarization on disconnect
        if user_uuid and user_uuid.strip():
            memory_client.force_session_summary(user_uuid, "auto_disconnect")
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
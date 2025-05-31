import json
import asyncio
import logging
import traceback
import threading
import queue
from typing import Optional, Dict, Set
import os
import datetime

from fastapi import WebSocket, WebSocketDisconnect

import config.runtime_config as runtime_config
from config import OPENAI_API_KEY, LOG_DIR
from vector.rag import log_debug, retrieve_documents
from memory.persistent_memory import append_to_summary, get_summary
from memory.session_memory import log_interaction, get_all_session_memory, store_session_prompt, force_session_summary
from stats.tools_dashboard import log_strategy_change, TOOL_STRATEGIES

logging.basicConfig(level=logging.DEBUG)

class SessionManager:
    """Manages active voice sessions and broadcasts strategy updates"""
    def __init__(self):
        self.voice_sessions: Dict[str, WebSocket] = {}
        self.dashboard_sessions: Set[WebSocket] = set()
        self.session_strategies: Dict[str, str] = {}

    async def add_voice_session(self, user_uuid: str, websocket: WebSocket, initial_strategy: str = "auto"):
        self.voice_sessions[user_uuid] = websocket
        self.session_strategies[user_uuid] = initial_strategy
        await self.broadcast_to_dashboards({
            "type": "session_connected",
            "user_uuid": user_uuid,
            "strategy": initial_strategy,
            "total_sessions": len(self.voice_sessions)
        })
        print(f"✅ Voice session added: {user_uuid} (strategy: {initial_strategy})")

    async def remove_voice_session(self, user_uuid: str):
        if user_uuid in self.voice_sessions:
            del self.voice_sessions[user_uuid]
        if user_uuid in self.session_strategies:
            del self.session_strategies[user_uuid]
        await self.broadcast_to_dashboards({
            "type": "session_disconnected", 
            "user_uuid": user_uuid,
            "total_sessions": len(self.voice_sessions)
        })
        print(f"🔌 Voice session removed: {user_uuid}")

    async def add_dashboard_session(self, websocket: WebSocket):
        self.dashboard_sessions.add(websocket)
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
        self.dashboard_sessions.discard(websocket)
        print(f"📊 Dashboard session removed (total: {len(self.dashboard_sessions)})")

    async def broadcast_strategy_update(self, new_strategy: str, source_dashboard: Optional[WebSocket] = None):
        updates_sent = 0
        failed_sessions = []
        for user_uuid, voice_websocket in self.voice_sessions.items():
            try:
                old_strategy = self.session_strategies.get(user_uuid, "auto")
                self.session_strategies[user_uuid] = new_strategy
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
        for user_uuid in failed_sessions:
            await self.remove_voice_session(user_uuid)
        await self.broadcast_to_dashboards({
            "type": "strategy_broadcast_completed",
            "new_strategy": new_strategy,
            "sessions_updated": updates_sent,
            "total_sessions": len(self.voice_sessions)
        }, exclude=source_dashboard)
        print(f"✅ Strategy broadcast completed: {updates_sent} sessions updated to '{new_strategy}'")
        return updates_sent

    async def broadcast_to_dashboards(self, message: dict, exclude: Optional[WebSocket] = None):
        failed_dashboards = []
        for dashboard_ws in self.dashboard_sessions:
            if dashboard_ws is exclude:
                continue
            try:
                await dashboard_ws.send_json(message)
            except Exception:
                failed_dashboards.append(dashboard_ws)
        for dashboard_ws in failed_dashboards:
            await self.remove_dashboard_session(dashboard_ws)

    def get_session_status(self):
        return {
            "voice_sessions": len(self.voice_sessions),
            "dashboard_sessions": len(self.dashboard_sessions),
            "session_strategies": self.session_strategies
        }

session_manager = SessionManager()

async def execute_tool(name: str, args: dict, user_uuid: Optional[str]):
    if name == "search_knowledge_base":
        query = args.get("query", "")
        print(f"🔍 Tool called: search_knowledge_base with query: '{query}'")
        import time
        start_time = time.time()
        docs = await retrieve_documents(query)
        end_time = time.time()
        timing_data = {"total": end_time - start_time, "retrieval": end_time - start_time, "gpt": 0.0, "tool": name}
        log_debug(query, docs[:3], "", timing_data)
        results = [{"content": d.get("text",""), "source": d.get("source",""), "relevance_score": d.get("score",0)} for d in docs[:3]]
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
        self.current_strategy = initial_strategy
        self.strategy_history = []
        self.incoming_queue = queue.Queue()
        self.outgoing_queue = queue.Queue()
        self.last_rag_injection_id: Optional[str] = None

    def update_strategy(self, new_strategy: str) -> bool:
        if new_strategy not in TOOL_STRATEGIES:
            print(f"❌ Invalid strategy: {new_strategy}")
            return False
        old_strategy = self.current_strategy
        self.current_strategy = new_strategy
        log_strategy_change(self.user_uuid, old_strategy, new_strategy)
        self.strategy_history.append({"timestamp": datetime.datetime.now().isoformat(), "old_strategy": old_strategy, "new_strategy": new_strategy})
        tool_choice = self.get_tool_choice_for_strategy(new_strategy)
        session_update = {"type": "session.update", "session": {"tool_choice": tool_choice}}
        if self.ws and self.connected:
            self.ws.send(json.dumps(session_update))
            print(f"🎛️ Strategy updated: {old_strategy} → {new_strategy} (tool_choice: {tool_choice})")
            return True
        else:
            print("⚠️ Cannot update strategy - not connected to OpenAI")
            return False

    def get_tool_choice_for_strategy(self, strategy: str) -> str:
        strategy_mapping = {"auto": "auto", "conservative": "auto", "aggressive": "auto", "none": "none", "required": "required"}
        return strategy_mapping.get(strategy, "auto")

    def get_enhanced_instructions(self, base_instructions: str, strategy: str) -> str:
        strategy_instructions = {
            "conservative": """
TOOL USAGE STRATEGY: Conservative
...
""",
            # include other strategies text blocks
        }
        strategy_text = strategy_instructions.get(strategy, strategy_instructions.get("auto", ""))
        return base_instructions + strategy_text

    def connect(self):
        url = f"wss://api.openai.com/v1/realtime?model={runtime_config.get('REALTIME_MODEL')}"
        headers = [f"Authorization: Bearer {self.api_key}", "OpenAI-Beta: realtime=v1"]
        print(f"🔗 Connecting to OpenAI: {url}")
        self.ws = websocket.WebSocketApp(url, header=headers, subprotocols=["realtime"], on_open=self.on_open, on_message=self.on_message, on_error=self.on_error, on_close=self.on_close)
        self.ws_thread = threading.Thread(target=self.ws.run_forever)
        self.ws_thread.daemon = True
        self.ws_thread.start()
        import time
        for _ in range(50):
            if self.connected:
                break
            time.sleep(0.1)
        return self.connected

    # ... include on_open, on_message, on_error, on_close, handle_function_call, send_message, get_message, close methods here ...

def detect_summary_request(message_text: str) -> bool:
    # function body as original
    pass

def log_voice_command_attempt(user_uuid: str, success: bool, reason: str = ""):
    # function body as original
    pass

async def process_user_message_enhanced(user_uuid: str, user_text: str, openai_client, websocket):
    # function body as original
    pass

def calculate_cost(input_tokens: int, output_tokens: int, model: str) -> float:
    # function body as original
    pass

def log_token_usage(user_uuid: str, input_tokens: int, output_tokens: int, model: str):
    # function body as original
    pass

async def realtime_chat(websocket: WebSocket):
    # Temporary stub: accept handshake, then close connection
    await websocket.accept()
    await websocket.close()

async def dashboard_websocket(websocket: WebSocket):
    # Temporary stub: accept handshake, then close connection
    await websocket.accept()
    await websocket.close()
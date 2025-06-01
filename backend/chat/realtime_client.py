import json
import os
import datetime
import time
import threading
import queue

from typing import Optional

import websocket

import config.runtime_config as runtime_config
from config import OPENAI_API_KEY
from vector.rag import log_debug, retrieve_documents
from memory.client import MemoryClient
from stats.tools_dashboard import log_strategy_change, TOOL_STRATEGIES


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

        self.memory = MemoryClient()

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
            on_close=self.on_close,
        )

        self.ws_thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.ws_thread.start()

        for _ in range(50):
            if self.connected:
                return True
            time.sleep(0.1)

        return False

    def on_open(self, ws):
        print("✅ Connected to OpenAI WebSocket")
        self.connected = True

        realtime_model = runtime_config.get("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
        realtime_voice = runtime_config.get("REALTIME_VOICE", "alloy")
        temperature = runtime_config.get("TEMPERATURE", 0.7)
        modalities = runtime_config.get("REALTIME_MODALITIES", ["text", "audio"])
        audio_format = runtime_config.get("REALTIME_AUDIO_FORMAT", "pcm16")
        turn_detection_type = runtime_config.get("TURN_DETECTION_TYPE", "server_vad")
        turn_detection_threshold = runtime_config.get("TURN_DETECTION_THRESHOLD", 0.5)
        turn_detection_silence_ms = runtime_config.get("TURN_DETECTION_SILENCE_MS", 200)
        tone_style = runtime_config.get("TONE_STYLE", "empathetic")

        context_parts = []

        persistent_summary = ""
        if self.user_uuid:
            persistent_summary = self.memory.get_summary(self.user_uuid) or ""
            if persistent_summary:
                context_parts.append(f"User Background:\n{persistent_summary}")

            session_memory = self.memory.get_session(self.user_uuid)
            if session_memory:
                conversation_context = []
                total_chars = 0
                session_limit = runtime_config.get("SESSION_MEMORY_CHAR_LIMIT", 15000)

                for interaction in reversed(session_memory):
                    role = interaction.get("role", "").title()
                    message = interaction.get("message", "")
                    interaction_text = f"{role}: {message}"

                    if total_chars + len(interaction_text) <= session_limit:
                        conversation_context.insert(0, interaction_text)
                        total_chars += len(interaction_text)
                    else:
                        break

                if conversation_context:
                    context_parts.append(
                        "Recent Conversation:\n" + "\n".join(conversation_context)
                    )

        base_instructions = runtime_config.get("SYSTEM_PROMPT", "").format(tone_style=tone_style)
        enhanced_instructions = self.get_enhanced_instructions(base_instructions, self.current_strategy)

        if context_parts:
            full_instructions = enhanced_instructions + f"\n\nContext about this user:\n\n{chr(10).join(context_parts)}"
        else:
            full_instructions = enhanced_instructions

        try:
            from config import LOG_DIR
            prompts_log_path = os.path.join(LOG_DIR, "actual_prompts.jsonl")

            with open(prompts_log_path, "a") as f:
                prompt_entry = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "user_uuid": self.user_uuid,
                    "final_prompt": full_instructions,
                    "prompt_length": len(full_instructions),
                    "estimated_tokens": len(full_instructions) // 4,
                    "strategy": self.current_strategy,
                    "model": realtime_model
                }
                f.write(json.dumps(prompt_entry) + "\n")
        except Exception as e:
            print(f"⚠️ Failed to log actual prompt: {e}")

        tool_choice = self.get_tool_choice_for_strategy(self.current_strategy)
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
                "tool_choice": tool_choice,
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
                                },
                                "k": {
                                    "type": "integer",
                                    "description": "Number of top results to return from the knowledge base (overrides default RAG_RESULT_COUNT)"
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
                                "information": {"type": "string", "description": "Important information to remember about the user (name, goals, preferences, etc.)"}
                            },
                            "required": ["information"]
                        }
                    }
                ]
            }
        }

        ws.send(json.dumps(session_config))
        print(f"📤 Session config sent: model={realtime_model}, strategy={self.current_strategy}, tool_choice={tool_choice}")

        try:
            prompt_data = {
                'system_prompt': base_instructions,
                'persistent_summary': persistent_summary if self.user_uuid else "",
                'session_context': '\n'.join(context_parts) if context_parts else "",
                'final_prompt': full_instructions,
                'prompt_length': len(full_instructions),
                'estimated_tokens': len(full_instructions) // 4,
                'strategy': self.current_strategy,
                'model': realtime_model
            }

            if self.user_uuid:
                self.memory.store_prompt(self.user_uuid, prompt_data)
                print(f"✅ Stored prompt data for {self.user_uuid}: {len(full_instructions)} chars")
        except Exception as e:
            print(f"⚠️ Failed to store prompt data: {e}")

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            msg_type = data.get('type', 'unknown')

            if self.user_uuid:
                if msg_type == "conversation.item.input_audio_transcription.completed":
                    transcript = data.get("transcript", "").strip()
                    if transcript:
                        print(f"💬 Logging user audio: {transcript[:100]}...")

                        if detect_summary_request(transcript):
                            print(f"🎯 VOICE COMMAND DETECTED in audio: {transcript}")

                            success = self.memory.force_session_summary(
                                self.user_uuid, "user_requested_voice_audio"
                            )

                            if success:
                                print(
                                    f"✅ Voice audio command success for {self.user_uuid}"
                                )
                                confirmation_message = "I've created a summary of our conversation and stored it in your persistent memory. You can continue our conversation and I'll remember the key points from what we discussed."

                                system_response = {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "message",
                                        "role": "system",
                                        "content": [{"type": "input_text", "text": f"Respond to the user with this exact message: '{confirmation_message}'"}]
                                    }
                                }

                                if ws and self.connected:
                                    ws.send(json.dumps(system_response))
                                    create_response = {"type": "response.create", "response": {"modalities": ["text", "audio"]}}
                                    ws.send(json.dumps(create_response))
                                    print(f"✅ Voice command confirmation sent via OpenAI for {self.user_uuid}")

                                return
                            else:
                                print(f"❌ Voice audio command failed for {self.user_uuid}")

                                error_message = "I wasn't able to create a summary right now. There might not be enough conversation content yet, or there was a technical issue."
                                error_response = {
                                    "type": "conversation.item.create",
                                    "item": {
                                        "type": "message",
                                        "role": "system",
                                        "content": [{"type": "input_text", "text": f"Respond to the user with this exact message: '{error_message}'"}]
                                    }
                                }

                                if ws and self.connected:
                                    ws.send(json.dumps(error_response))
                                    create_response = {"type": "response.create", "response": {"modalities": ["text", "audio"]}}
                                    ws.send(json.dumps(create_response))

                                return

                        self.memory.log_interaction(self.user_uuid, "user", transcript)

                elif msg_type == "conversation.item.created":
                    item = data.get("item", {})
                    if item.get("type") == "message":
                        role = item.get("role")
                        if role == "user":
                            content = ""
                            if item.get("content"):
                                for content_part in item["content"]:
                                    if content_part.get("type") in ("input_text", "text"):
                                        content = content_part.get("text", "")
                                        break

                            if content:
                                print(f"💬 Logging user text: {content[:100]}...")

                            if detect_summary_request(content):
                                print(f"🎯 VOICE COMMAND in text message: '{content}'")

                                success = self.memory.force_session_summary(
                                    self.user_uuid, "user_requested_text"
                                )

                                if success:
                                    print(f"✅ Text voice command success for {self.user_uuid}")
                                    return
                                else:
                                    print(f"❌ Text voice command failed for {self.user_uuid}")

                            self.memory.log_interaction(self.user_uuid, "user", content)

                        elif role == "assistant":
                            content = ""
                            if item.get("content"):
                                for content_part in item["content"]:
                                    if content_part.get("type") == "text":
                                        content += content_part.get("text", "")

                            if content:
                                print(f"💬 Logging assistant message: {content[:100]}...")
                            self.memory.log_interaction(self.user_uuid, "assistant", content)

                elif msg_type == "response.audio_transcript.done":
                    transcript = data.get("transcript", "").strip()
                    if transcript:
                        print(f"💬 Logging assistant audio transcript: {transcript[:100]}...")
                        self.memory.log_interaction(self.user_uuid, "assistant", transcript)

            if msg_type == "response.function_call_arguments.done":
                print(f"🔧 Function call: {data.get('name')}")
                def handle_async_function_call():
                    import asyncio
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(self.handle_function_call(data))
                    loop.close()

                threading.Thread(target=handle_async_function_call, daemon=True).start()

        except Exception as e:
            print(f"❌ Error in on_message: {e}")
            import traceback
            traceback.print_exc()

        # Enqueue raw message for downstream forwarding (unless intercepted above)
        try:
            self.incoming_queue.put(message)
        except Exception:
            # Swallow any queue errors
            pass

    def on_error(self, ws, error):
        pass

    def on_close(self, ws, code, msg):
        self.connected = False

    def send_message(self, message: str) -> bool:
        if self.ws and self.connected:
            self.ws.send(message)
            return True
        return False

    def get_message(self):
        try:
            return self.incoming_queue.get_nowait()
        except Exception:
            return None

    def close(self):
        if self.ws:
            self.ws.close()

    async def handle_function_call(self, data):
        """
        Handle function call events from OpenAI (e.g., search_knowledge_base, update_user_memory).
        """
        try:
            function_name = data.get("name")
            arguments = data.get("arguments", {})
            # parse JSON-encoded argument string if needed
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    arguments = {}
            response = None

            if function_name == "search_knowledge_base":
                # Handle OpenAI function call for RAG search
                query = arguments.get("query", "")
                if query:
                    # Optional override for number of results
                    k = arguments.get("k")
                    docs = await retrieve_documents(query, k)
                    call_id = data.get("call_id")
                    # Send function call output back into the conversation
                    response_event = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(docs)
                        }
                    }
                    if self.ws and self.connected:
                        self.ws.send(json.dumps(response_event))
                        # Resume generation after function call
                        create_resp = {
                            "type": "response.create",
                            "response": {"modalities": runtime_config.get("REALTIME_MODALITIES", ["text", "audio"])}
                        }
                        self.ws.send(json.dumps(create_resp))
                    return
            elif function_name == "update_user_memory":
                # Handle user memory update function call
                information = arguments.get("information", "")
                if information and self.user_uuid:
                    self.memory.append_summary(self.user_uuid, information)
                    call_id = data.get("call_id")
                    response_event = {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps("User memory updated.")
                        }
                    }
                    if self.ws and self.connected:
                        self.ws.send(json.dumps(response_event))
                        create_resp = {
                            "type": "response.create",
                            "response": {"modalities": runtime_config.get("REALTIME_MODALITIES", ["text", "audio"])}
                        }
                        self.ws.send(json.dumps(create_resp))
                    return
            else:
                # Handle unknown function calls gracefully
                call_id = data.get("call_id")
                response_event = {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(f"Unknown function: {function_name}")
                    }
                }
                if self.ws and self.connected:
                    self.ws.send(json.dumps(response_event))
                    create_resp = {
                        "type": "response.create",
                        "response": {"modalities": runtime_config.get("REALTIME_MODALITIES", ["text", "audio"])}
                    }
                    self.ws.send(json.dumps(create_resp))
                return

            if response and self.ws and self.connected:
                self.ws.send(json.dumps(response))
        except Exception as e:
            print(f"❌ Error in handle_function_call: {e}")

def detect_summary_request(message_text: str) -> bool:
    """
    Enhanced detection of user requesting conversation summary with comprehensive logging
    """
    if not message_text or not isinstance(message_text, str):
        return False

    summary_triggers = [
        "summarize our conversation",
        "summarize what we discussed", 
        "give me a summary",
        "summarize this conversation",
        "create a summary",
        "can you summarize",
        "summarize what we talked about",
        "sum up our chat",
        "recap our conversation",
        "make a summary",
        "provide a summary",
        "conversation summary",
        "recap what we discussed",
        "sum up what we said",
        "give me a recap"
    ]

    message_lower = message_text.lower().strip()

    for trigger in summary_triggers:
        if trigger in message_lower:
            print(f"🎯 VOICE COMMAND DETECTED: '{trigger}' in message: '{message_text[:100]}...'")
            return True

    summary_keywords = ["summary", "summarize", "recap", "sum up"]
    if any(keyword in message_lower for keyword in summary_keywords):
        print(f"🔍 POTENTIAL SUMMARY REQUEST (not triggered): '{message_text[:100]}...'")

    return False
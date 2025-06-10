# runtime_config.py
"""
Simple runtime configuration management for Mobeus Assistant
"""
import os
import json
from typing import Any, Dict
from pathlib import Path

# In-memory config store
_config_store: Dict[str, Any] = {}

# Default configuration values
DEFAULT_CONFIG = {
    "SESSION_MEMORY_CHAR_LIMIT": 15000,
    "PROMPT_HISTORY_DEPTH": 5,
    "TONE_STYLE": "empathetic",
    "GPT_MODEL": "gpt-4",
    "TEMPERATURE": 0.7,
    "RAG_RESULT_COUNT": 5,
    "EMBED_MODEL": "text-embedding-3-small",
    "RAG_TEMPERATURE": 0.3,
    
    # Realtime settings
    "REALTIME_MODEL": "gpt-4o-realtime-preview-2024-12-17",
    "REALTIME_VOICE": "alloy",
    "REALTIME_AUDIO_FORMAT": "pcm16",
    "REALTIME_MODALITIES": ["text", "audio"],
    
    # Turn detection
    "TURN_DETECTION_TYPE": "server_vad",
    "TURN_DETECTION_THRESHOLD": 0.5,
    "TURN_DETECTION_SILENCE_MS": 200,

    # D-ID settings
    "VIDEO_MODE_ENABLED": False,
    "DID_USE_AUDIO": False,  # False = text mode (faster), True = audio mode (preserves voice)
    "DID_VOICE_ID": "en-US-JennyNeural",
    "DID_VOICE_PROVIDER": "microsoft",
    "DID_VOICE_STYLE": "Friendly",
    "DID_EXPRESSION": "neutral",
    "DID_EXPRESSION_INTENSITY": 1.0,  # Expression intensity (0.0 to 1.0)
    "DID_STITCH": True,
    "DID_MAX_POLL_TIME": 20,
    "DID_POLL_INTERVAL": 0.5,
    "DID_IDLE_VIDEO_URL": "https://create-images-results.d-id.com/DefaultPresenters/Zivva_f/idle.mp4",  # Replace with actual idle video

    # Video/Avatar settings
    "VIDEO_PROVIDER": "d-id",
    "DID_API_BASE_URL": "https://api.d-id.com",
    "DID_AVATAR_SOURCE_URL": "https://create-images-results.d-id.com/DefaultPresenters/Zivva_f/thumbnail.jpeg",
    "DID_AVATAR_NAME": "Zivva",
    "DID_CONNECTION_TIMEOUT": 30,
    "DID_STREAM_TIMEOUT": 300,

    # Ngrok settings
    "BACKEND_WEBHOOK_URL": "http://backend:8010",  # Default for internal use


    "SYSTEM_PROMPT": """You are Mobeus, an AI assistant developed by the Mobeus team. You specialize in helping users with questions about Mobeus products, services, and capabilities.

    Key facts about you:
    - You are Mobeus (not Claude, ChatGPT, or any other assistant)
    - You have access to a comprehensive knowledge base about Mobeus through the search_knowledge_base function
    - When users ask about Mobeus, always search the knowledge base for accurate, up-to-date information
    - You can remember important information about users through the update_user_memory function

    Your personality style is {tone_style}. Respond accordingly:
    - empathetic: Be caring, understanding, and emotionally supportive
    - casual: Be friendly, relaxed, and conversational  
    - professional: Be precise, formal, and business-focused
    - friendly: Be warm, upbeat, and enthusiastic
    - concise: Be direct, brief, and to-the-point

    Always search the knowledge base when users ask about:
    - Mobeus products, features, or capabilities
    - Technical questions about Mobeus systems
    - Company information, team, or background
    - Pricing, plans, or business details

    Use the update_user_memory function to remember:
    - User's name, job, location, or personal details
    - Their goals, projects, or ongoing needs
    - Important preferences or requirements
    - Any significant context for future conversations

    Keep your responses natural and conversational. Avoid being overly repetitive or verbose.""",
}

def _load_from_env():
    """Load configuration from environment variables"""
    # Start with defaults
    global _config_store
    _config_store = DEFAULT_CONFIG.copy()
    
    # Override with environment variables if they exist
    for key, default_value in DEFAULT_CONFIG.items():
        env_value = os.getenv(key)
        if env_value is not None:
            # Try to convert to appropriate type
            if isinstance(default_value, bool):
                _config_store[key] = env_value.lower() in ('true', '1', 'yes', 'on')
            elif isinstance(default_value, int):
                try:
                    _config_store[key] = int(env_value)
                except ValueError:
                    print(f"⚠️ Warning: Could not parse {key}={env_value} as int, using default")
                    _config_store[key] = default_value
            elif isinstance(default_value, float):
                try:
                    _config_store[key] = float(env_value)
                except ValueError:
                    print(f"⚠️ Warning: Could not parse {key}={env_value} as float, using default")
                    _config_store[key] = default_value
            elif isinstance(default_value, list):
                try:
                    # Try to parse as JSON first
                    if env_value.startswith('[') or env_value.startswith('"['):
                        _config_store[key] = json.loads(env_value)
                    else:
                        # Fallback to comma-separated
                        _config_store[key] = [x.strip() for x in env_value.split(',')]
                except (json.JSONDecodeError, ValueError):
                    print(f"⚠️ Warning: Could not parse {key}={env_value} as list, using default")
                    _config_store[key] = default_value
            else:
                # Handle strings, including JSON-encoded multi-line strings
                if env_value.startswith('"') and env_value.endswith('"'):
                    try:
                        _config_store[key] = json.loads(env_value)
                    except json.JSONDecodeError:
                        # Fallback to raw string without quotes
                        _config_store[key] = env_value[1:-1] if len(env_value) > 1 else env_value
                else:
                    _config_store[key] = env_value

def get(key: str, default: Any = None) -> Any:
    """Get a configuration value"""
    if not _config_store:
        _load_from_env()
    return _config_store.get(key, default)

def set_config(key: str, value: Any) -> None:
    """Set a configuration value"""
    if not _config_store:
        _load_from_env()
    _config_store[key] = value

def all_config() -> Dict[str, Any]:
    """Get all configuration values"""
    if not _config_store:
        _load_from_env()
    return _config_store.copy()

def to_env_file(filepath: str = ".env") -> None:
    """Save current config to .env file with proper escaping"""
    if not _config_store:
        _load_from_env()
    
    # Read existing .env file
    existing_lines = []
    env_path = Path(filepath)
    if env_path.exists():
        with open(env_path, 'r') as f:
            existing_lines = f.readlines()
    
    # Update or add config values
    config_keys_handled = set()
    updated_lines = []
    
    for line in existing_lines:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            key = line.split('=')[0].strip()
            if key in _config_store:
                # Update existing value with proper escaping
                value = _config_store[key]
                escaped_value = _escape_env_value(value)
                updated_lines.append(f"{key}={escaped_value}")
                config_keys_handled.add(key)
            else:
                # Keep existing line as-is
                updated_lines.append(line)
        else:
            # Keep comments and empty lines
            updated_lines.append(line)
    
    # Add new config values that weren't in the file
    for key, value in _config_store.items():
        if key not in config_keys_handled:
            escaped_value = _escape_env_value(value)
            updated_lines.append(f"{key}={escaped_value}")
    
    # Write updated .env file
    with open(env_path, 'w') as f:
        for line in updated_lines:
            f.write(line + '\n')
    
    print(f"✅ Configuration saved to {filepath}")
    
def _escape_env_value(value: Any) -> str:
    """Properly escape values for .env file"""
    if isinstance(value, list):
        return json.dumps(value)
    elif isinstance(value, str):
        # Handle multi-line strings by escaping newlines and quotes
        if '\n' in value or '"' in value or "'" in value:
            # Use JSON encoding for complex strings
            return json.dumps(value)
        else:
            # Simple strings can use quotes
            return f'"{value}"'
    else:
        return str(value)

def reset_to_defaults() -> None:
    """Reset all configuration to default values"""
    global _config_store
    _config_store = DEFAULT_CONFIG.copy()

# Force initialization on import
_config_store = {}
_load_from_env()
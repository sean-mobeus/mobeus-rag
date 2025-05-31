"""OpenAI Realtime API constants and supported parameters"""
"""
OpenAI Realtime API constants and supported parameters
"""

# Supported voices for Realtime API
REALTIME_VOICES = [
    "alloy",
    "ash", 
    "ballad",
    "coral",
    "echo",
    "sage",
    "shimmer",
    "verse"
]

# Supported models for Realtime API
REALTIME_MODELS = [
    "gpt-4o-realtime-preview-2024-12-17",
    "gpt-4o-mini-realtime-preview-2024-12-17"
]

# Supported audio formats
REALTIME_AUDIO_FORMATS = [
    "pcm16",
    "g711_ulaw",
    "g711_alaw"
]

# Supported modalities
REALTIME_MODALITIES = [
    ["text"],
    ["audio"], 
    ["text", "audio"]
]

# Default configuration
DEFAULT_REALTIME_CONFIG = {
    "model": "gpt-4o-realtime-preview-2024-12-17",
    "voice": "alloy",
    "modalities": ["text", "audio"],
    "input_audio_format": "pcm16",
    "output_audio_format": "pcm16",
    "turn_detection": {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 200
    }
}
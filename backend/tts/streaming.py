import httpx
from typing import Generator
from config import OPENAI_API_KEY

OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"

# Create a persistent HTTP client that can reuse connections
persistent_client = httpx.Client(
    timeout=60.0,
    limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
)

def stream_tts_from_openai(text: str, voice: str = "nova") -> Generator[bytes, None, None]:
    """
    Stream text-to-speech from OpenAI's API with optimized response time.
    
    Uses a persistent HTTP client to reduce connection overhead.
    Now uses a single request approach to avoid playback issues.
    """
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    
    # FIXED: No longer making two requests - just one optimized request
    payload = {
        "model": "tts-1",
        "input": text,
        "voice": voice,
        "response_format": "mp3",
        "stream": True,
    }
    
    # Use the persistent client to avoid TCP handshake overhead
    with persistent_client.stream("POST", OPENAI_TTS_URL, headers=headers, json=payload, timeout=60.0) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            if chunk:
                yield chunk
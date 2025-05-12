import httpx
from typing import Generator
from config import OPENAI_API_KEY

OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"

def stream_tts_from_openai(text: str, voice: str = "nova") -> Generator[bytes, None, None]:
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "tts-1",
        "input": text,
        "voice": voice,
        "response_format": "opus",
        "stream": True,
    }

    with httpx.stream("POST", OPENAI_TTS_URL, headers=headers, json=payload, timeout=60.0) as response:
        response.raise_for_status()
        for chunk in response.iter_bytes():
            if chunk:
                yield chunk
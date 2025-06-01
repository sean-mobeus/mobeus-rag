"""
Streaming utilities for audio services (TTS).
"""
from io import BytesIO

from openai import OpenAI

from config import OPENAI_API_KEY
import config.runtime_config as runtime_config


def synthesize_audio_tts(text: str, voice: str = None) -> bytes:
    """
    Generate TTS audio bytes using OpenAI Audio Speech API.
    """
    client = OpenAI(api_key=OPENAI_API_KEY)
    model = runtime_config.get("TTS_MODEL", "tts-1")
    tts_voice = voice or runtime_config.get("TTS_VOICE", "nova")
    # Call the OpenAI TTS endpoint
    response = client.audio.speech.create(
        model=model,
        voice=tts_voice,
        input=text
    )
    # Read the entire audio stream (e.g. MP3)
    audio_bytes = BytesIO(response.read()).getvalue()
    return audio_bytes
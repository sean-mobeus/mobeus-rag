from abc import ABC, abstractmethod

from .streaming import synthesize_audio_tts


class BaseAudioProvider(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: str = None, format: str = None) -> bytes:
        """
        Generate full audio bytes for the given text.
        """
        ...

    @abstractmethod
    async def stream(self, text: str, voice: str = None, format: str = None):
        """
        Stream audio frames for the given text.
        Yields raw audio bytes (e.g. MP3 or PCM).
        """
        ...


class OpenAITTSProvider(BaseAudioProvider):
    """
    Audio provider using OpenAI Audio TTS REST API (audio.speech.create).
    """

    async def synthesize(self, text: str, voice: str = None, format: str = None) -> bytes:
        """
        Generate full audio for the provided text using the configured TTS model.
        """
        return synthesize_audio_tts(text, voice)

    async def stream(self, text: str, voice: str = None, format: str = None):
        """
        Stream the full audio as a single frame. Stub for future real-time support.
        """
        data = await self.synthesize(text, voice, format)
        yield data
import io
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any

import openai
from openai import AsyncOpenAI

from config import OPENAI_API_KEY


class BaseSpeechRecognizer(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes) -> str:
        """
        Perform one-off transcription of the given audio bytes.
        """
        ...

    @abstractmethod
    def stream_recognize(self, frames) -> AsyncGenerator[dict[str, Any], Any]:
        """
        Perform streaming transcription over an async iterator of audio frames.
        Yields dicts with keys {'text', 'final', 'turn_boundary'}.
        """
        ...


class WhisperRecognizer(BaseSpeechRecognizer):
    """
    Speech recognizer using OpenAI Whisper via REST API for transcription.
    """

    def __init__(self, model: str = "whisper-1"):
        openai.api_key = OPENAI_API_KEY
        self.model = model

    async def transcribe(self, audio_bytes: bytes) -> str:
        """
        Transcribe the full audio bytes and return the text.
        """
        file_obj = io.BytesIO(audio_bytes)
        client   = AsyncOpenAI(api_key=OPENAI_API_KEY)
        response = await client.audio.transcriptions.create(
            file=file_obj,
            model=self.model,
        )
        return response.text


    async def stream_recognize(self, frames):
        """
        Real-time streaming recognizer via OpenAI Realtime WebSocket.
        Sends audio frames to the Realtime API and yields intermediate and final transcripts.
        """
        import json, threading, time, asyncio, queue
        import websocket
        from config.runtime_config import get as _get_config

        class _ASRClient:
            def __init__(self, api_key: str | None, model: str):
                if api_key is None:
                    raise ValueError("OPENAI_API_KEY must be set for streaming recognition")
                self.api_key = api_key
                self.model = model
                self.realtime_model = _get_config("REALTIME_MODEL")
                self.voice = _get_config("REALTIME_VOICE")
                self.audio_format = _get_config("REALTIME_AUDIO_FORMAT")
                self.turn_type = _get_config("TURN_DETECTION_TYPE")
                self.turn_threshold = _get_config("TURN_DETECTION_THRESHOLD")
                self.turn_silence_ms = _get_config("TURN_DETECTION_SILENCE_MS")
                self.ws = None
                self.incoming = queue.Queue()
                self.connected = False

            def on_open(self, ws):
                config = {
                    "type": "session.update",
                    "session": {
                        "model": self.realtime_model,
                        "voice": self.voice,
                        "modalities": [],  # only transcription events
                        "input_audio_format": self.audio_format,
                        "output_audio_format": self.audio_format,
                        "input_audio_transcription": {"model": self.model},
                        "turn_detection": {
                            "type": self.turn_type,
                            "threshold": self.turn_threshold,
                            "silence_duration_ms": self.turn_silence_ms,
                            "prefix_padding_ms": 300,
                        },
                    },
                }
                ws.send(json.dumps(config))
                self.connected = True

            def on_message(self, ws, message):
                try:
                    self.incoming.put(json.loads(message))
                except Exception:
                    pass

            def on_error(self, ws, error):
                pass

            def on_close(self, ws, code, msg):
                self.connected = False

            def connect(self):
                url = f"wss://api.openai.com/v1/realtime?model={self.realtime_model}"
                headers = [
                    f"Authorization: Bearer {self.api_key}",
                    "OpenAI-Beta: realtime=v1",
                ]
                self.ws = websocket.WebSocketApp(
                    url,
                    header=headers,
                    subprotocols=["realtime"],
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close,
                )
                thread = threading.Thread(target=self.ws.run_forever, daemon=True)
                thread.start()
                for _ in range(50):
                    if self.connected:
                        return True
                    time.sleep(0.1)
                return False

            def send_audio(self, chunk: bytes):
                if self.ws and self.connected:
                    self.ws.send(chunk, opcode=websocket.ABNF.OPCODE_BINARY)

            def get_message(self):
                try:
                    return self.incoming.get_nowait()
                except Exception:
                    return None

            def close(self):
                if self.ws:
                    self.ws.close()

        client = _ASRClient(OPENAI_API_KEY, self.model)
        if not client.connect():
            raise RuntimeError("Failed to connect to OpenAI Realtime API for speech recognition")

        try:
            async for chunk in frames:
                client.send_audio(chunk)
            while client.connected or not client.incoming.empty():
                msg = client.get_message()
                if not msg:
                    await asyncio.sleep(0.01)
                    continue
                msg_type = msg.get("type", "")
                if msg_type == "conversation.item.input_audio_transcription.partial":
                    yield {"text": msg.get("transcript", ""), "final": False, "turn_boundary": False}
                elif msg_type == "conversation.item.input_audio_transcription.completed":
                    yield {"text": msg.get("transcript", ""), "final": True, "turn_boundary": True}
        finally:
            client.close()
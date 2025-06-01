from fastapi import APIRouter, UploadFile, File, WebSocket, WebSocketDisconnect
from speech_recognition.recognizer import WhisperRecognizer

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"service": "speech_recognition", "status": "healthy"}


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Perform one-off transcription of uploaded audio file."""
    content = await file.read()
    recognizer = WhisperRecognizer()
    transcript = await recognizer.transcribe(content)
    return {"transcript": transcript, "turns": []}


@router.websocket("/stream")
async def speech_stream(websocket: WebSocket):
    """WebSocket endpoint for streaming audio transcription."""
    await websocket.accept()
    recognizer = WhisperRecognizer()
    buffer = bytearray()
    try:
        while True:
            chunk = await websocket.receive_bytes()
            buffer.extend(chunk)
    except WebSocketDisconnect:
        pass
    # Transcribe accumulated audio frames
    text = await recognizer.transcribe(bytes(buffer))
    await websocket.send_json({"text": text, "final": True, "turn_boundary": True})
    await websocket.close()

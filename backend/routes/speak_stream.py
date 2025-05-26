# speak_stream.py - Optimized version
from fastapi import APIRouter, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from tts.streaming import stream_tts_from_openai
import time
import asyncio
from vector.rag import log_debug

router = APIRouter()


@router.get("/api/speak-stream")
def speak_stream(background_tasks: BackgroundTasks, text: str = Query(...), voice: str = "nova"):
    """
    Stream audio from OpenAI TTS using MP3 format with optimized buffering.
    
    Key optimizations:
    1. No initial buffering delay - send chunks as soon as they arrive
    2. Track performance metrics
    3. Better error handling
    """
    start_time = time.time()
    
    # Create a generator that yields audio chunks with timing info
    def optimized_generator():
        first_chunk_time = None
        chunk_count = 0
        total_bytes = 0
        
        try:
            # Get the audio stream and start sending immediately
            for chunk in stream_tts_from_openai(text, voice):
                chunk_count += 1
                total_bytes += len(chunk)
                
                # Record timing for the first chunk (critical for latency measurement)
                if not first_chunk_time:
                    first_chunk_time = time.time()
                    latency = first_chunk_time - start_time
                    print(f"⚡ First TTS chunk: {latency:.2f}s ({len(chunk)} bytes)")
                
                # Send the chunk immediately
                yield chunk
                
            # Log completion
            end_time = time.time()
            print(f"✅ TTS complete: {end_time - start_time:.2f}s total, {chunk_count} chunks, {total_bytes} bytes")
            
        except Exception as e:
            end_time = time.time()
            print(f"❌ TTS error after {end_time - start_time:.2f}s: {str(e)}")
            raise
        finally:
            # Always log performance data
            end_time = time.time()
            total_time = end_time - start_time
            first_chunk_latency = (first_chunk_time - start_time) if first_chunk_time else None
            
            # Use background task to avoid blocking the response
            if background_tasks:
                background_tasks.add_task(
                    log_debug,
                    query=text,
                    chunks=[],
                    answer="(streamed audio)",
                    timings={
                        "tts_total": total_time,
                        "tts_first_chunk": first_chunk_latency,
                        "tts_completion": total_time,
                        "tts_bytes": total_bytes,
                        "tts_chunks": chunk_count
                    }
                )

    # Use MP3 content type for browser compatibility
    return StreamingResponse(
        optimized_generator(), 
        media_type="audio/mpeg",
        headers={
            "X-Accel-Buffering": "no",  # Disable proxy buffering
            "Cache-Control": "no-cache",  # Prevent caching
        }
    )
# streaming_rag.py - Implement streaming responses
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
import asyncio
import time
import json
from openai import AsyncOpenAI
from config import OPENAI_API_KEY, DEBUG_LOG_PATH
import logging
import os

# Initialize OpenAI client
client = AsyncOpenAI(api_key=OPENAI_API_KEY)

router = APIRouter()

async def stream_rag_response(query, retrieval_results):
    """Stream the RAG response as it's being generated."""
    
    # Construct the GPT prompt with context from retrieval
    context = "\n\n".join([chunk["text"] for chunk in retrieval_results["chunks"]])
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant. Answer based on the provided context. Keep initial responses concise and fast, expanding details afterward."},
        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
    ]
    
    # Start streaming the response
    stream = await client.chat.completions.create(
        model="gpt-3.5-turbo",  # Consider using 3.5 for faster responses
        messages=messages,
        stream=True,
        temperature=0.3,  # Lower temperature for faster responses
        max_tokens=500    # Limit response length for faster completion
    )
    
    full_response = ""
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            content = chunk.choices[0].delta.content
            full_response += content
            # Yield chunks as they arrive
            yield content
    
    # Log the full response for debugging
    with open(DEBUG_LOG_PATH, "a") as f:
        log_entry = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "query": query,
            "answer": full_response,
            "timings": retrieval_results["timings"],
            "top_chunks": retrieval_results["chunks"]
        }
        f.write(json.dumps(log_entry) + "\n")

@router.post("/api/stream-query")
async def stream_query(request: Request):
    """Endpoint that streams the answer as it's generated."""
    data = await request.json()
    query = data.get("query", "")
    
    if not query:
        return {"error": "Missing query parameter"}
    
    # Record start time
    start_time = time.time()
    
    # Import your existing retrieval function
    from rag import retrieve_documents
    
    # Run retrieval
    retrieval_start = time.time()
    documents = await retrieve_documents(query)
    retrieval_time = time.time() - retrieval_start
    
    # Prepare retrieval results with timing
    retrieval_results = {
        "chunks": documents,
        "timings": {
            "total": 0,  # Will be updated at the end
            "retrieval": retrieval_time,
            "gpt": 0,    # Will be updated as we stream
        }
    }
    
    # Start streaming response
    async def generate():
        gpt_start = time.time()
        try:
            async for text_chunk in stream_rag_response(query, retrieval_results):
                # Update timing information
                current_time = time.time()
                retrieval_results["timings"]["gpt"] = current_time - gpt_start
                retrieval_results["timings"]["total"] = current_time - start_time
                
                # Send chunk
                yield f"data: {json.dumps({'chunk': text_chunk, 'timings': retrieval_results['timings']})}\n\n"
                
            # Send end marker
            yield f"data: {json.dumps({'done': True})}\n\n"
        except Exception as e:
            logging.error(f"Error in streaming: {str(e)}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            
    return StreamingResponse(generate(), media_type="text/event-stream")
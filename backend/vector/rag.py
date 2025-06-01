import os
import time
import json
import datetime
from openai import OpenAI
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from typing import cast
from chromadb.api.types import EmbeddingFunction, Embeddable
from config import OPENAI_API_KEY, CHROMA_DB_DIR, EMBED_MODEL, DEBUG_LOG_PATH
from config import runtime_config
from memory.session_memory import get_all_session_memory, get_memory_stats
from memory.persistent_memory import get_summary

# Print debug information about the environment
print(f"🔍 RAG Module Debug: Log path is {DEBUG_LOG_PATH}")
print(f"🔍 RAG Module Debug: Log directory exists: {os.path.exists(os.path.dirname(DEBUG_LOG_PATH))}")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

chroma_client = PersistentClient(path=CHROMA_DB_DIR)
# Debug: verify ChromaDB directory path and existence
print(f"🔍 ChromaDB directory: {CHROMA_DB_DIR}, exists: {os.path.exists(CHROMA_DB_DIR)}")
# Create and cast embedding function to satisfy type checker requirements
embed_model = runtime_config.get("EMBED_MODEL", "text-embedding-3-small")
_embedding_fn = OpenAIEmbeddingFunction(api_key=OPENAI_API_KEY, model_name=embed_model)
_embedding_fn_cast: EmbeddingFunction[Embeddable] = cast(EmbeddingFunction[Embeddable], _embedding_fn)
collection = chroma_client.get_or_create_collection(
    name="mobeus_knowledge",
    embedding_function=_embedding_fn_cast
)

# Write a test entry to verify logging works immediately
try:
    print(f"💾 Writing test log entry to {DEBUG_LOG_PATH}")
    with open(DEBUG_LOG_PATH, "a") as f:
        test_entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "message": "RAG module loaded and logging system initialized"
        }
        f.write(json.dumps(test_entry) + "\n")
    print(f"✅ Test log entry written successfully")
except Exception as e:
    print(f"❌ Failed to write test log entry: {e}")

def log_debug(query, chunks, answer, timings):
    """
    Write debug logs to the configured debug log file.
    Ensures the file exists and properly appends without creating duplicates.
    
    Args:
        query: The query being answered
        chunks: The retrieved document chunks
        answer: The generated answer
        timings: Dictionary of timing information
    """
    try:
        print(f"📝 Attempting to log query: '{query[:30]}...' to {DEBUG_LOG_PATH}")
        # Check if the directory exists and create it if needed
        log_dir = os.path.dirname(DEBUG_LOG_PATH)
        if log_dir and not os.path.exists(log_dir):
            print(f"📁 Creating log directory: {log_dir}")
            os.makedirs(log_dir, exist_ok=True)
            
        # Create the entry to log
        entry = json.dumps({
            "timestamp": datetime.datetime.now().isoformat(),
            "query": query,
            "top_chunks": chunks,
            "answer": answer,
            "timings": timings
        })
        
        # Write to the log file, ensuring we append
        with open(DEBUG_LOG_PATH, "a") as f:
            f.write(entry + "\n")
        print(f"✅ Successfully logged query to {DEBUG_LOG_PATH}")   
    except Exception as e:
        print(f"⚠️ Warning: Failed to write to debug log: {e}")

from typing import Optional

def query_rag(query: str, uuid: str) -> dict:
    """
    Enhanced RAG query that uses runtime config and new memory system
    """
    # Get config values (will update in real-time!)
    rag_result_count = runtime_config.get("RAG_RESULT_COUNT", 5)
    rag_temperature = runtime_config.get("RAG_TEMPERATURE", 0.3)
    gpt_model = runtime_config.get("GPT_MODEL", "gpt-4")
    tone_style = runtime_config.get("TONE_STYLE", "empathetic")
    
    print(f"🎛️ Using RAG config: {rag_result_count} results, temp={rag_temperature}, model={gpt_model}")
    
    # Get vector results using config
    results = collection.query(
        query_texts=[query], 
        n_results=rag_result_count  # Now configurable!
    )
    
    # Build context using new memory system
    context_parts = []
    
    # 1. Add persistent memory summary
    persistent_summary = get_summary(uuid)
    if persistent_summary:
        context_parts.append(f"User Background: {persistent_summary}")
    
    # 2. Add ALL session memory (character-based, not count-based)
    session_memory = get_all_session_memory(uuid)
    if session_memory:
        conversation_context = []
        for interaction in session_memory:
            role = interaction["role"].title()
            message = interaction["message"]
            conversation_context.append(f"{role}: {message}")
        
        context_parts.append("Recent Conversation:\n" + "\n".join(conversation_context))
    
    # 3. Add RAG results
    if results and results['documents'] and results['documents'][0]:
        rag_context = "\n".join(results['documents'][0])
        context_parts.append(f"Relevant Information:\n{rag_context}")
    
    # Build final prompt with tone
    full_context = "\n\n".join(context_parts)
    
    # Create system message based on tone config
    tone_prompts = {
        "empathetic": "You are a caring, empathetic assistant who understands user emotions and responds with warmth.",
        "casual": "You are a friendly, casual assistant who speaks naturally and conversationally.",
        "professional": "You are a professional, precise assistant who provides clear and authoritative responses.",
        "friendly": "You are an upbeat, friendly assistant who is enthusiastic about helping.",
        "concise": "You are a direct, concise assistant who provides efficient and to-the-point responses."
    }
    
    system_message = tone_prompts.get(tone_style, tone_prompts["empathetic"])
    
    # Call OpenAI with config values
    response = openai_client.chat.completions.create(
        model=gpt_model,  # Configurable model
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": f"Context:\n{full_context}\n\nQuery: {query}"}
        ],
        temperature=rag_temperature  # Configurable temperature
    )
    
    answer = response.choices[0].message.content
    
    # Get memory stats for debugging
    memory_stats = get_memory_stats(uuid)

    def safe_get_sources(results):
        """Safely extract sources from ChromaDB results"""
        if not results:
            return []
    
        metadatas = results.get('metadatas')
        if not metadatas or not isinstance(metadatas, list) or len(metadatas) == 0:
            return []
    
        first_metadata_list = metadatas[0]
        if not first_metadata_list or not isinstance(first_metadata_list, list):
            return []
    
        return first_metadata_list
    
    return {
        "answer": answer,
        "sources": safe_get_sources(results),
        "config_used": {
            "model": gpt_model,
            "temperature": rag_temperature,
            "results_count": rag_result_count,
            "tone": tone_style
        },
        "memory_stats": memory_stats
    }

async def retrieve_documents(query: str, n_results: int | None = None):
    # Determine number of results from runtime config if not specified
    if n_results is None:
        # Read default RAG result count from runtime config
        n_results = runtime_config.get("RAG_RESULT_COUNT", 5)
    # Ensure n_results is always an int and not None
    if n_results is None:
        raise ValueError("n_results cannot be None")
    n_results = int(n_results)
    results = collection.query(query_texts=[query], n_results=n_results)
    documents = results.get("documents")
    texts = documents[0] if documents and len(documents) > 0 and documents[0] is not None else []
    metadatas_list = results.get("metadatas")
    metadatas = metadatas_list[0] if metadatas_list and len(metadatas_list) > 0 and metadatas_list[0] is not None else []
    chunks = []
    for idx, text in enumerate(texts):
        meta = metadatas[idx] if idx < len(metadatas) else {}
        # Merge text with metadata in a type-safe manner
        if isinstance(meta, dict):
            chunk = {"text": text, **meta}
        else:
            chunk = {"text": text}
        chunks.append(chunk)
    return chunks
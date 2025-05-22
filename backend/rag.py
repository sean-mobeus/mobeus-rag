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
from agents.tone_engine import get_tone_shaping_chunks
from memory.session_memory import get_recent_interactions
from memory.persistent_memory import get_summary

# Print debug information about the environment
print(f"🔍 RAG Module Debug: Log path is {DEBUG_LOG_PATH}")
print(f"🔍 RAG Module Debug: Log directory exists: {os.path.exists(os.path.dirname(DEBUG_LOG_PATH))}")

openai_client = OpenAI(api_key=OPENAI_API_KEY)

chroma_client = PersistentClient(path=CHROMA_DB_DIR)
# Create and cast embedding function to satisfy type checker requirements
_embedding_fn = OpenAIEmbeddingFunction(api_key=OPENAI_API_KEY, model_name=EMBED_MODEL)
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

def query_rag(query: str, uuid: Optional[str] = None):
    start_time = time.time()

    retrieval_start = time.time()
    results = collection.query(query_texts=[query], n_results=5)
    retrieval_end = time.time()

    documents = results.get("documents")
    metadatas = results.get("metadatas")
    if documents and len(documents) > 0 and documents[0] is not None:
        retrieved_chunks = documents[0]
    else:
        retrieved_chunks = []
    if metadatas and len(metadatas) > 0 and metadatas[0] is not None:
        sources = metadatas[0]
    else:
        sources = []
    context = "\n\n".join(retrieved_chunks)

    tone_start = time.time()
    tone_chunks = get_tone_shaping_chunks(query, top_k=3)
    tone_end = time.time()
    tone_prefix = "\n".join([f"TONE GUIDELINE: {chunk}" for chunk in tone_chunks])

    memory_prefix = ""
    if uuid:
        summary = get_summary(uuid)
        history = get_recent_interactions(uuid, limit=5)
        memory_lines = [f"{item['role'].capitalize()}: {item['message']}" for item in history]

        memory_blocks = []
        if summary:
            memory_blocks.append(f"Long-term summary:\n{summary}")
        if memory_lines:
            memory_blocks.append("Recent conversation:\n" + "\n".join(memory_lines))

        memory_prefix = "\n\n".join(memory_blocks) + "\n"

    prompt = f"""{tone_prefix}

{memory_prefix}
Use the following information to answer the question.
If the answer is not fully contained, try to summarize what's known or likely.

Context:
{context}

Question:
{query}

Answer:"""

    gpt_start = time.time()
    chat_response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    gpt_end = time.time()

    answer = chat_response.choices[0].message.content
    total_time = time.time() - start_time

    log_debug(query, sources, answer, {
        "total": total_time,
        "retrieval": retrieval_end - retrieval_start,
        "tone": tone_end - tone_start,
        "gpt": gpt_end - gpt_start
    })

    return {
        "answer": answer,
        "sources": sources
    }
 
async def retrieve_documents(query: str):
    results = collection.query(query_texts=[query], n_results=5)
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

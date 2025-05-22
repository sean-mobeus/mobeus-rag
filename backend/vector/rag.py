import time
import json
import datetime
from openai import OpenAI
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from config import OPENAI_API_KEY, CHROMA_DB_DIR, EMBED_MODEL, DEBUG_LOG_PATH
from chat.agents.tone_engine import get_tone_shaping_chunks
from memory.session_memory import get_recent_interactions
from memory.persistent_memory import get_summary

openai_client = OpenAI(api_key=OPENAI_API_KEY)

chroma_client = PersistentClient(path=CHROMA_DB_DIR)
collection = chroma_client.get_or_create_collection(
    name="mobeus_knowledge",
    embedding_function=OpenAIEmbeddingFunction(api_key=OPENAI_API_KEY, model_name=EMBED_MODEL)
)

def log_debug(query, chunks, answer, timings):
    with open(DEBUG_LOG_PATH, "a") as f:
        f.write(json.dumps({
            "timestamp": datetime.datetime.now().isoformat(),
            "query": query,
            "top_chunks": chunks,
            "answer": answer,
            "timings": timings
        }) + "\n")

def query_rag(query: str, uuid: str = None):
    start_time = time.time()

    retrieval_start = time.time()
    results = collection.query(query_texts=[query], n_results=5)
    retrieval_end = time.time()

    retrieved_chunks = results["documents"][0]
    sources = results["metadatas"][0]
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
    texts = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    chunks = []
    for idx, text in enumerate(texts):
        meta = metadatas[idx] if idx < len(metadatas) else {}
        chunk = {"text": text}
        if isinstance(meta, dict):
            chunk.update(meta)
        chunks.append(chunk)
    return chunks

import time
import json
import datetime
from openai import OpenAI
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from config import OPENAI_API_KEY, CHROMA_DB_DIR, EMBED_MODEL, DEBUG_LOG_PATH
from agents.tone_engine import get_tone_shaping_chunks

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

def query_rag(query: str):
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

    prompt = f"""{tone_prefix}

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

    # ✅ Logging here
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
    """
    Retrieve top knowledge-base chunks for the given query.
    Returns a list of dicts, each containing 'text' and any metadata fields.
    """
    # Query ChromaDB for the top results
    results = collection.query(query_texts=[query], n_results=5)
    texts = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    # Combine text and metadata into chunk dicts
    chunks = []
    for idx, text in enumerate(texts):
        meta = metadatas[idx] if idx < len(metadatas) else {}
        chunk = {"text": text}
        if isinstance(meta, dict):
            chunk.update(meta)
        chunks.append(chunk)
    return chunks
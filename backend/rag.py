from openai import OpenAI
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from config import OPENAI_API_KEY, CHROMA_DB_DIR, EMBED_MODEL
import datetime
import json


openai_client = OpenAI(api_key=OPENAI_API_KEY)

chroma_client = PersistentClient(path=CHROMA_DB_DIR)
collection = chroma_client.get_or_create_collection(
    name="mobeus_knowledge",
    embedding_function=OpenAIEmbeddingFunction(api_key=OPENAI_API_KEY, model_name=EMBED_MODEL)
)

def query_rag(query: str):
    results = collection.query(query_texts=[query], n_results=5)

    def log_debug(query, chunks, answer):
        with open("debug_log.jsonl", "a") as f:
            f.write(json.dumps({
                "timestamp": datetime.datetime.now().isoformat(),
                "query": query,
                "top_chunks": chunks,
                "answer": answer
            }) + "\n")

    print("🔎 RAG Search Results:")
    print(results)
    retrieved_chunks = results["documents"][0]
    sources = results["metadatas"][0]

    context = "\n\n".join(retrieved_chunks)
    prompt = f"""Use the following information to answer the question.
If the answer is not fully contained, try to summarize what's known or likely.'

Context:
{context}

Question:
{query}

Answer:"""

    chat_response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2
    )
    answer = chat_response.choices[0].message.content

    log_debug(query, sources, answer)

    return {
        "answer": answer,
        "sources": sources
    }
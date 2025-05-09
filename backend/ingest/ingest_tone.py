# ingest_tone.py
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import json
from pathlib import Path
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from backend.config import OPENAI_API_KEY, CHROMA_DB_DIR, EMBED_MODEL

# === CONFIG ===
JSONL_PATH = Path("docs/tone_shaper.jsonl")
COLLECTION_NAME = "conversation_tone"

def read_jsonl_chunks(jsonl_path):
    with open(jsonl_path, "r", encoding="utf-8") as f:
        return [json.loads(line.strip()) for line in f if line.strip()]

def embed_and_store(chunks):
    print(f"📦 Connecting to Chroma at {CHROMA_DB_DIR}...")
    client = PersistentClient(path=CHROMA_DB_DIR)

    try:
        print(f"🧹 Deleting old collection (if exists)...")
        client.delete_collection(COLLECTION_NAME)
    except Exception as e:
        print(f"⚠️ Skipped delete: {e}")

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name=EMBED_MODEL
        )
    )

    print(f"🔢 Embedding {len(chunks)} tone brief entries...")
    for i, chunk in enumerate(chunks):
        metadata = chunk.get("metadata", {})
        collection.add(
            documents=[chunk["text"]],
            metadatas=[metadata],
            ids=[f"{COLLECTION_NAME}_{i}"]
        )
        if i % 5 == 0 or i == len(chunks) - 1:
            print(f"✅ {i+1}/{len(chunks)} embedded")

if __name__ == "__main__":
    chunks = read_jsonl_chunks(JSONL_PATH)
    embed_and_store(chunks)
    print("🎯 Tone ingestion complete.")
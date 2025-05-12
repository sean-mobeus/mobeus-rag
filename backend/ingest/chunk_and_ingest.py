import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import json
import tiktoken
from pathlib import Path
from docx import Document
from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from config import OPENAI_API_KEY, CHROMA_DB_DIR, EMBED_MODEL

# === CONFIG ===
DOCS_DIR = Path("docs")
CHUNK_SIZE = 512
CHUNK_OVERLAP = 128
MIN_TOKENS = 20

encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")

def num_tokens(text):
    return len(encoding.encode(text))

def sliding_window_chunks(text, chunk_size, overlap):
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        if num_tokens(chunk) >= MIN_TOKENS:
            chunks.append(chunk)
        start += chunk_size - overlap
    return chunks

def extract_clean_chunks(doc_path):
    doc = Document(doc_path)
    doc_name = doc_path.stem
    current_section = ""
    injected_context = "Mobeus"
    text_buffer = []
    all_chunks = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text or "...(existing content)..." in text:
            continue

        # Catch inline pseudo-headings like "Telecom:"
        if ":" in text and para.style.name not in ("Heading 1", "Heading 2", "Heading 3") and text.split(":")[0].lower() in ["telecom", "finance", "government", "insurance", "automotive", "education", "retail"]:
            current_section = text.split(":")[0].strip().title()

        if para.style.name.startswith("Heading"):
            if text_buffer:
                full_text = " ".join(text_buffer)
                for chunk in sliding_window_chunks(full_text, CHUNK_SIZE, CHUNK_OVERLAP):
                    all_chunks.append({
                        "doc_name": doc_name,
                        "section_title": current_section,
                        "content": f"{injected_context} — {current_section}:\n{chunk}"
                    })
                text_buffer = []
            current_section = text
        else:
            text_buffer.append(text)

    if text_buffer:
        full_text = " ".join(text_buffer)
        for chunk in sliding_window_chunks(full_text, CHUNK_SIZE, CHUNK_OVERLAP):
            all_chunks.append({
                "doc_name": doc_name,
                "section_title": current_section,
                "content": f"{injected_context} — {current_section}:\n{chunk}"
            })

    return all_chunks

def embed_and_store(chunks):
    print(f"📦 Connecting to Chroma at {CHROMA_DB_DIR}...")
    client = PersistentClient(path=CHROMA_DB_DIR)

    print(f"🧹 Deleting old collection (if exists)...")
    try:
        client.delete_collection("mobeus_knowledge")
    except Exception as e:
        print(f"⚠️ Skipping delete: {e}")

    collection = client.create_collection(
        name="mobeus_knowledge",
        embedding_function=OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name=EMBED_MODEL
        )
    )

    print(f"🔢 Embedding {len(chunks)} chunks...")
    for i, chunk in enumerate(chunks):
        metadata = {
            "doc_name": chunk["doc_name"],
            "section_title": chunk["section_title"]
        }
        collection.add(
            documents=[chunk["content"]],
            metadatas=[metadata],
            ids=[f"{chunk['doc_name']}_{i}"]
        )
        if i % 10 == 0 or i == len(chunks) - 1:
            print(f"✅ {i+1}/{len(chunks)} chunks ingested")

if __name__ == "__main__":
    print("📂 Reading and chunking documents...")
    all_chunks = []
    print("📁 Looking in:", DOCS_DIR)
    print("📄 Files found:", list(DOCS_DIR.glob("*")))

    for doc_path in DOCS_DIR.glob("*.docx"):
        chunks = extract_clean_chunks(doc_path)
        print(f"➡️  {doc_path.name}: {len(chunks)} chunks")
        all_chunks.extend(chunks)

    print(f"🧠 Total chunks: {len(all_chunks)}")
    embed_and_store(all_chunks)
    print("🎉 Ingestion complete.")

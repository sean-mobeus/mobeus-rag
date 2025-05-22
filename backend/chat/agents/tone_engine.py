from chromadb import PersistentClient
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from config import OPENAI_API_KEY, CHROMA_DB_DIR, EMBED_MODEL

def get_tone_shaping_chunks(prompt_text: str, top_k=3):
    client = PersistentClient(path=CHROMA_DB_DIR)
    collection = client.get_collection(
        name="conversation_tone",
        embedding_function=OpenAIEmbeddingFunction(
            api_key=OPENAI_API_KEY,
            model_name=EMBED_MODEL
        )
    )
    results = collection.query(query_texts=[prompt_text], n_results=top_k)
    return results['documents'][0] if results and results['documents'] else []
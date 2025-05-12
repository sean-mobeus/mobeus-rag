# config.py
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_DB_DIR = "./chroma"
EMBED_MODEL = "text-embedding-3-small"
DEBUG_LOG_PATH = os.getenv("MOBEUS_DEBUG_LOG", os.path.join(os.getcwd(), "rag_debug_fresh.jsonl"))

# config.py
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_DB_DIR = "./chroma"
EMBED_MODEL = "text-embedding-3-small"
<<<<<<< Updated upstream
DEBUG_LOG_PATH = os.getenv("MOBEUS_DEBUG_LOG", os.path.join(os.getcwd(), "rag_debug_fresh.jsonl"))
=======
DEBUG_LOG_PATH = os.getenv("MOBEUS_DEBUG_LOG", os.path.join(os.getcwd(), "rag_debug_fresh.jsonl"))
>>>>>>> Stashed changes

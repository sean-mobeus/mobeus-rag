# config.py
import os

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_DB_DIR = "./chroma"
EMBED_MODEL = "text-embedding-3-small"
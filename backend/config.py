import os
from dotenv import load_dotenv

load_dotenv()

# Determine if running in Docker based on environment
IN_DOCKER = os.getenv("MOBEUS_DEBUG") == "true"

# OpenAI API Key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# ChromaDB directory - path is relative to current working directory
CHROMA_DB_DIR = os.getenv("CHROMA_DB_DIR", "../chroma")

# OpenAI Embedding Model - use the current model from your config
EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-3-small")

# Log filename from environment (or default)
LOG_FILENAME = os.getenv("MOBEUS_DEBUG_LOG", "rag_debug.jsonl")

# Debug log path - handle Docker vs local paths correctly
if IN_DOCKER:
    # When in Docker, ALWAYS use the mounted logs directory
    LOG_DIR = "/app/logs"
    DEBUG_LOG_PATH = os.path.join(LOG_DIR, LOG_FILENAME)
    print(f"🐳 Docker environment detected. Debug logs will be written to: {DEBUG_LOG_PATH}")
else:
    # For local development, use current directory or logs subdirectory
    LOG_DIR = os.getenv("MOBEUS_LOG_DIR", "logs")
    DEBUG_LOG_PATH = os.path.join(LOG_DIR, LOG_FILENAME)
    print(f"💻 Local environment detected. Debug logs will be written to: {DEBUG_LOG_PATH}")

# Ensure logs directory exists in both environments
try:
    if not os.path.exists(os.path.dirname(DEBUG_LOG_PATH)):
        os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
        print(f"📁 Created logs directory: {os.path.dirname(DEBUG_LOG_PATH)}")
except Exception as e:
    print(f"⚠️ Warning: Could not create logs directory: {e}")

# Print confirmation of final log path
print(f"📝 Debug logs will be written to: {DEBUG_LOG_PATH}")
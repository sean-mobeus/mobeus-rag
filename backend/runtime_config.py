# runtime_config.py
import os
from dotenv import dotenv_values

CONFIG = {
    "SESSION_MEMORY_CHAR_LIMIT": int(os.getenv("SESSION_MEMORY_CHAR_LIMIT", 15000)),
    "GPT_MODEL": os.getenv("GPT_MODEL", "gpt-4"),
    "PROMPT_HISTORY_DEPTH": int(os.getenv("PROMPT_HISTORY_DEPTH", 5)),
    "TONE_STYLE": os.getenv("TONE_STYLE", "empathetic"),
}

def get(key: str):
    return CONFIG.get(key)

def set(key: str, value):
    if key in CONFIG:
        if key in ["SESSION_MEMORY_CHAR_LIMIT", "PROMPT_HISTORY_DEPTH"]:
            CONFIG[key] = int(value)
        else:
            CONFIG[key] = value

def all_config():
    return CONFIG.copy()

def to_env_file(path=".env"):
    existing = dotenv_values(path)
    updated = {**existing, **CONFIG}
    lines = [f"{k}={v}" for k, v in updated.items()]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
import psycopg2
import os
from datetime import datetime


DB_PARAMS = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", 5432),
    "dbname": os.getenv("POSTGRES_DB", "mobeus"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "password")
}

def save_summary(uuid: str, summary: str):
    """
    Persist a long-term summary for the given session UUID.
    TODO: implement actual storage (e.g., separate DB table or file store).
    """
    pass

def get_summary(uuid: str):
    """
    Retrieve the persisted summary for the given session UUID.
    Returns None if no summary is available.
    """
    return None

DB_PARAMS = {
    "host": os.getenv("POSTGRES_HOST", "localhost"),
    "port": os.getenv("POSTGRES_PORT", 5432),
    "dbname": os.getenv("POSTGRES_DB", "mobeus"),
    "user": os.getenv("POSTGRES_USER", "postgres"),
    "password": os.getenv("POSTGRES_PASSWORD", "password")
}

MEMORY_CHAR_LIMIT = int(os.getenv("SESSION_MEMORY_CHAR_LIMIT", 15000))


def get_connection():
    return psycopg2.connect(**DB_PARAMS)

def init_persistent_table():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS persistent_memory (
                    uuid TEXT PRIMARY KEY,
                    summary TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

def save_summary(uuid: str, summary: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO persistent_memory (uuid, summary, updated_at)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON CONFLICT (uuid) DO UPDATE SET summary = EXCLUDED.summary, updated_at = CURRENT_TIMESTAMP;
            """, (uuid, summary))
            conn.commit()

def get_summary(uuid: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT summary FROM persistent_memory WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
            return row[0] if row else None


def init_session_table():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_memory (
                    id SERIAL PRIMARY KEY,
                    uuid TEXT NOT NULL,
                    role TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

def summarize_and_clear(uuid: str):
    history = get_recent_interactions(uuid, limit=100)
    if not history:
        return

    lines = [f"{item['role'].capitalize()}: {item['message']}" for item in history]
    summary_input = "\n".join(lines)

    from openai import OpenAI
    from config import OPENAI_API_KEY
    openai_client = OpenAI(api_key=OPENAI_API_KEY)

    completion = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Summarize the following conversation into a single paragraph that retains key intent and tone."},
            {"role": "user", "content": summary_input}
        ],
        temperature=0.3
    )
    summary = completion.choices[0].message.content
    save_summary(uuid, summary)

    # Clear old session memory
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM session_memory WHERE uuid = %s", (uuid,))
            conn.commit()

def get_total_char_count(uuid: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT SUM(CHAR_LENGTH(message)) FROM session_memory WHERE uuid = %s", (uuid,))
            result = cur.fetchone()
            return result[0] or 0

def log_interaction(uuid: str, role: str, message: str):
    # Check capacity before logging
    total_chars = get_total_char_count(uuid)
    if total_chars >= MEMORY_CHAR_LIMIT:
        summarize_and_clear(uuid)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO session_memory (uuid, role, message)
                VALUES (%s, %s, %s);
            """, (uuid, role, message))
            conn.commit()

def get_recent_interactions(uuid: str, limit: int = 5):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, message FROM session_memory
                WHERE uuid = %s
                ORDER BY created_at DESC
                LIMIT %s;
            """, (uuid, limit))
            rows = cur.fetchall()
            return list(reversed([{"role": r, "message": m} for r, m in rows]))

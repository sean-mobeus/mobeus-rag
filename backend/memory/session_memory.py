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

def get_connection():
    return psycopg2.connect(**DB_PARAMS)

def init_session_table():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS session_memory (
                    id SERIAL PRIMARY KEY,
                    uuid TEXT NOT NULL,
                    role TEXT NOT NULL,  -- 'user' or 'assistant'
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

def log_interaction(uuid: str, role: str, message: str):
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
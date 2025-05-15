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

def init_user_table():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    uuid TEXT PRIMARY KEY,
                    name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

def upsert_user(uuid: str, name: str = None):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO users (uuid, name)
                VALUES (%s, %s)
                ON CONFLICT (uuid) DO UPDATE SET name = EXCLUDED.name;
            """, (uuid, name))
            conn.commit()

def get_user(uuid: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT uuid, name, created_at FROM users WHERE uuid = %s", (uuid,))
            row = cur.fetchone()
            if row:
                return {"uuid": row[0], "name": row[1], "created_at": row[2].isoformat()}
            return None
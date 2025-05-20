
# backend/memory/user_identity.py
"""
User identity management module
"""
import os
from datetime import datetime
from typing import Optional, Dict, Any
from memory.db import get_connection, execute_db_operation, ensure_tables_exist

def init_user_table():
    """
    Initialize the users table
    This is now handled by the centralized db module
    """
    from memory.db import init_user_table
    init_user_table()

def _upsert_user_impl(uuid: str, name: str):
    """Implementation of upsert_user without error handling"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (uuid, name)
                VALUES (%s, %s)
                ON CONFLICT (uuid) DO UPDATE
                SET name = EXCLUDED.name
                """,
                (uuid, name)
            )
            conn.commit()

def upsert_user(uuid: str, name: str):
    """
    Insert or update user information.
    """
    return execute_db_operation(_upsert_user_impl, uuid, name)

def _get_user_impl(uuid: str) -> Optional[Dict[str, Any]]:
    """Implementation of get_user without error handling"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT uuid, name, created_at FROM users WHERE uuid = %s",
                (uuid,)
            )
            row = cur.fetchone()
            if row:
                return {
                    "uuid": row[0],
                    "name": row[1],
                    "created_at": row[2].isoformat() if row[2] else None
                }
            return None

def get_user(uuid: str) -> Optional[Dict[str, Any]]:
    """
    Get user information by UUID.
    Returns user dict if found, None otherwise.
    """
    return execute_db_operation(_get_user_impl, uuid)
"""
Session memory management module
"""
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from memory.db import get_connection, execute_db_operation, ensure_tables_exist

def init_session_table():
    """
    Initialize the session_memory table
    This is now handled by the centralized db module
    """
    from memory.db import init_session_table
    init_session_table()

def _log_interaction_impl(uuid: str, role: str, message: str):
    """Implementation of log_interaction without error handling"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO session_memory (uuid, role, message)
                VALUES (%s, %s, %s);
            """, (uuid, role, message))
            conn.commit()

def log_interaction(uuid: str, role: str, message: str):
    """
    Log a user or assistant interaction
    Now with automatic error handling and table creation
    """
    return execute_db_operation(_log_interaction_impl, uuid, role, message)

def _get_recent_interactions_impl(uuid: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Implementation of get_recent_interactions without error handling"""
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

def get_recent_interactions(uuid: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Get recent interactions for a user
    Now with automatic error handling and table creation
    """
    return execute_db_operation(_get_recent_interactions_impl, uuid, limit)
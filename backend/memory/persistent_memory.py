# backend/memory/persistent_memory.py
"""
Persistent memory management for long-term user summaries
"""
from .db import get_connection, execute_db_operation
from typing import Optional

def _get_summary_impl(uuid: str) -> Optional[str]:
    """Implementation of get_summary without error handling"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT summary FROM persistent_memory WHERE uuid = %s",
                (uuid,)
            )
            row = cur.fetchone()
            return row[0] if row and row[0] is not None else None

def get_summary(uuid: str) -> Optional[str]:
    """
    Get long-term summary for a user/session.
    Returns the summary text if it exists, otherwise None.
    """
    return execute_db_operation(_get_summary_impl, uuid)

def _append_to_summary_impl(uuid: str, new_info: str):
    """Implementation of append_to_summary without error handling"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Get current summary
            cur.execute(
                "SELECT summary FROM persistent_memory WHERE uuid = %s",
                (uuid,)
            )
            row = cur.fetchone()
            current_summary = row[0] if row and row[0] else ""
            
            # Append new information
            if current_summary:
                updated_summary = f"{current_summary}\n{new_info}"
            else:
                updated_summary = new_info
            
            # Update the summary
            cur.execute(
                """
                INSERT INTO persistent_memory (uuid, summary)
                VALUES (%s, %s)
                ON CONFLICT (uuid) DO UPDATE
                SET summary = EXCLUDED.summary,
                    updated_at = CURRENT_TIMESTAMP
                """, (uuid, updated_summary)
            )
            conn.commit()

def append_to_summary(uuid: str, new_info: str):
    """
    Append new information to existing summary.
    If no summary exists, creates a new one.
    """
    return execute_db_operation(_append_to_summary_impl, uuid, new_info)

def _clear_summary_impl(uuid: str):
    """Implementation of clear_summary without error handling"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM persistent_memory WHERE uuid = %s",
                (uuid,)
            )
            conn.commit()

def clear_summary(uuid: str):
    """
    Clear all persistent memory for a user.
    Returns True if successful, False otherwise.
    """
    try:
        execute_db_operation(_clear_summary_impl, uuid)
        return True
    except Exception as e:
        print(f"❌ Error clearing persistent memory for {uuid}: {e}")
        return False
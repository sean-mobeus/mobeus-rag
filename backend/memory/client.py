"""
High-level client for session and persistent memory operations.
"""
from typing import Any, Dict, List, Optional

from .db import get_connection, execute_db_operation
from .session_memory import (
    log_interaction,
    get_session_memory_size,
    get_all_session_memory,
    format_conversation_for_summary,
    clear_session_memory,
    log_summarization_event,
    store_session_prompt,
    debug_prompt_storage,
)
from .persistent_memory import (
    get_summary,
    append_to_summary,
    clear_summary,
)
from .user_identity import upsert_user, get_user


class MemoryClient:
    """Client to manage session and persistent memory operations."""

    def __init__(self):
        # Table initialization is handled by execute_db_operation wrapper.
        pass

    def log_interaction(self, uuid: str, role: str, message: str) -> Any:
        """Log a user or assistant interaction."""
        return log_interaction(uuid, role, message)

    def get_session_size(self, uuid: str) -> int:
        """Return total character count of session memory for a user."""
        return get_session_memory_size(uuid)

    def get_session(self, uuid: str) -> List[Dict[str, Any]]:
        """Return all session memory entries for a user."""
        return get_all_session_memory(uuid) or []

    def clear_session(self, uuid: str) -> Any:
        """Clear all session memory for a user."""
        return clear_session_memory(uuid)

    def summarize_conversation(self, uuid: str) -> str:
        """Format conversation text for summarization."""
        return format_conversation_for_summary(uuid)

    def store_prompt(self, uuid: str, prompt_data: Dict[str, Any]) -> Any:
        """Store session prompt details for debugging."""
        return store_session_prompt(uuid, prompt_data)

    def debug_prompt_storage(self, uuid: str) -> Any:
        """Return debug info for stored prompts for a session."""
        return debug_prompt_storage(uuid)

    def get_conversation_data(self, uuid: str) -> Dict[str, Any]:
        """Return current session and recent historical interaction data."""
        # inline historical retrieval as in legacy code
        def _get_historical() -> List[Dict[str, Any]]:
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """\
                        SELECT user_message, assistant_response, created_at, interaction_id
                        FROM interaction_logs
                        WHERE uuid = %s
                        ORDER BY created_at DESC
                        LIMIT 5
                        """,
                        (uuid,),
                    )
                    rows = cur.fetchall()
            return [
                {
                    "user_message": row[0][:100] + "..." if row[0] and len(row[0]) > 100 else row[0],
                    "assistant_response": row[1][:100] + "..." if row[1] and len(row[1]) > 100 else row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "interaction_id": row[3],
                }
                for row in rows
            ]

        conversation = self.get_session(uuid)
        historical = execute_db_operation(_get_historical) or []
        return {
            "uuid": uuid,
            "current_session_count": len(conversation),
            "current_session_preview": conversation[:2],
            "historical_interactions_count": len(historical),
            "historical_interactions_preview": historical,
        }

    def get_summary(self, uuid: str) -> Optional[str]:
        """Return the long-term summary for a user."""
        return get_summary(uuid)

    def append_summary(self, uuid: str, new_info: str) -> Any:
        """Append information to the persistent memory summary."""
        return append_to_summary(uuid, new_info)

    def clear_summary(self, uuid: str) -> Any:
        """Clear the persistent memory summary for a user."""
        return clear_summary(uuid)

    def upsert_user(self, uuid: str, name: str) -> Any:
        """Insert or update user information."""
        return upsert_user(uuid, name)

    def get_user(self, uuid: str) -> Optional[Dict[str, Any]]:
        """Retrieve user information by UUID."""
        return get_user(uuid)

    def force_session_summary(self, uuid: str, reason: str = "user_requested") -> bool:
        """Force summarization of current session memory and archive it to persistent memory."""
        from .session_memory import force_session_summary

        return force_session_summary(uuid, reason)
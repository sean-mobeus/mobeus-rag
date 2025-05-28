"""
Enhanced session memory management with character-based limits and auto-summarization
"""
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from memory.db import get_connection, execute_db_operation
import runtime_config
import json

# Default summarization prompt
DEFAULT_SUMMARY_PROMPT = """Please summarize the following conversation between a user and an AI assistant. Focus on:

1. **Personal Information**: Name, job, location, family, friends, interests, preferences
2. **User's Goals & Inquiries**: What they're trying to achieve, questions they've asked
3. **Key Context**: Important facts, decisions made, ongoing projects or topics
4. **Conversation Patterns**: How they prefer to communicate, their expertise level
5. **Action Items**: Any tasks, follow-ups, or commitments mentioned

Keep the summary concise but comprehensive. Maintain the user's voice and perspective where relevant.

Conversation to summarize:
{conversation_text}

Summary:"""

def get_session_memory_limit() -> int:
    """Get current session memory character limit from config"""
    return runtime_config.get("SESSION_MEMORY_CHAR_LIMIT", 12000)

def get_summary_prompt() -> str:
    """Get summarization prompt from config"""
    return runtime_config.get("SESSION_SUMMARY_PROMPT", DEFAULT_SUMMARY_PROMPT)

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
    Log a user or assistant interaction with automatic memory management
    """
    # Log the new interaction
    result = execute_db_operation(_log_interaction_impl, uuid, role, message)
    
    # Check if we need to summarize and clean up
    check_and_manage_memory(uuid)
    
    return result

def _get_session_memory_size_impl(uuid: str) -> int:
    """Get total character count of session memory for a user"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COALESCE(SUM(LENGTH(role) + LENGTH(message) + 4), 0) as total_chars
                FROM session_memory
                WHERE uuid = %s
            """, (uuid,))
            row = cur.fetchone()
            return row[0] if row else 0

def get_session_memory_size(uuid: str) -> int:
    """Get total character count of session memory for a user"""
    return execute_db_operation(_get_session_memory_size_impl, uuid)

def _get_all_session_memory_impl(uuid: str) -> List[Dict[str, Any]]:
    """Get ALL session memory for a user (not limited by count)"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT role, message, created_at FROM session_memory
                WHERE uuid = %s
                ORDER BY created_at ASC
            """, (uuid,))
            rows = cur.fetchall()
            return [{"role": r, "message": m, "created_at": c} for r, m, c in rows]

def get_all_session_memory(uuid: str) -> List[Dict[str, Any]]:
    """
    Get ALL session memory for a user (character-based, not count-based)
    """
    return execute_db_operation(_get_all_session_memory_impl, uuid)

def _format_conversation_for_summary_impl(uuid: str) -> str:
    """Format conversation for summarization"""
    interactions = get_all_session_memory(uuid)
    conversation_lines = []
    
    for interaction in interactions:
        role = interaction["role"].title()  # User/Assistant
        message = interaction["message"]
        conversation_lines.append(f"{role}: {message}")
    
    return "\n".join(conversation_lines)

def format_conversation_for_summary(uuid: str) -> str:
    """Format conversation text for summarization"""
    return execute_db_operation(_format_conversation_for_summary_impl, uuid)

def _clear_session_memory_impl(uuid: str):
    """Clear all session memory for a user"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM session_memory WHERE uuid = %s", (uuid,))
            conn.commit()

def clear_session_memory(uuid: str):
    """Clear all session memory for a user"""
    return execute_db_operation(_clear_session_memory_impl, uuid)

def check_and_manage_memory(uuid: str):
    """
    Check if session memory needs to be summarized and managed
    This is called after each interaction
    """
    memory_size = get_session_memory_size(uuid)
    limit = get_session_memory_limit()
    
    # If we're approaching the limit (90% of max), trigger summarization
    if memory_size >= (limit * 0.9):
        print(f"📝 Session memory for {uuid} approaching limit ({memory_size}/{limit} chars). Triggering summarization...")
        summarize_and_archive_session(uuid, "auto_limit")

def log_summarization_event(uuid: str, event_type: str, details: Optional[dict] = None):
    """Log summarization events for dashboard visibility"""
    with open("summarization_events.jsonl", "a") as f:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_uuid": uuid,
            "event_type": event_type,  # "auto_limit", "auto_disconnect", "manual_tool"
            "details": details or {}
        }
        f.write(json.dumps(entry) + "\n")

def summarize_and_archive_session(uuid: str, reason: str = "auto_limit"):
    """
    Summarize current session memory and move it to persistent memory
    """
    try:
        # Get conversation text for summarization
        conversation_text = format_conversation_for_summary(uuid)
        print(f"📝 CONVERSATION LENGTH: {len(conversation_text)} chars")
        
        if not conversation_text.strip():
            print(f"⚠️ No conversation to summarize for {uuid}")
            return
        
        print(f"📝 GENERATING SUMMARY for {uuid}...")
        # Generate summary using OpenAI
        summary = generate_conversation_summary(conversation_text)
        print(f"📝 SUMMARY GENERATED: {len(summary) if summary else 0} chars")
        
        if summary:
            # Store summary in persistent memory
            from memory.persistent_memory import append_to_summary
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            summary_with_timestamp = f"[{timestamp}] {summary}"
            print(f"📝 STORING SUMMARY in persistent memory for {uuid}")
            append_to_summary(uuid, summary_with_timestamp)
            
            # LOG THE EVENT
            log_summarization_event(uuid, reason, {
                "conversation_length": len(conversation_text),
                "summary_length": len(summary),
                "timestamp": timestamp
            })
            
            # Clear session memory
            print(f"📝 CLEARING SESSION MEMORY for {uuid}")
            clear_session_memory(uuid)
            
            print(f"✅ Session memory summarized and archived for {uuid}")
        else:
            print(f"⚠️ Failed to generate summary for {uuid}")
            
    except Exception as e:
        print(f"❌ Error summarizing session for {uuid}: {e}")
        import traceback
        traceback.print_exc()

def generate_conversation_summary(conversation_text: str) -> Optional[str]:
    """
    Generate a summary of the conversation using OpenAI
    """
    try:
        from openai import OpenAI
        from config import OPENAI_API_KEY
        
        client = OpenAI(api_key=OPENAI_API_KEY)
        
        # Get model and temperature from config
        model = runtime_config.get("GPT_MODEL", "gpt-4")
        temperature = runtime_config.get("TEMPERATURE", 0.3)  # Lower temp for consistent summaries
        
        # Format the prompt
        prompt = get_summary_prompt().format(conversation_text=conversation_text)
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that creates concise, comprehensive conversation summaries."},
                {"role": "user", "content": prompt}
            ],
            temperature=temperature,
            max_tokens=1000  # Reasonable limit for summaries
        )
        
        content = response.choices[0].message.content
        summary = content.strip() if content is not None else None
        return summary
        
    except Exception as e:
        print(f"❌ Error generating summary: {e}")
        return None

def get_memory_stats(uuid: str) -> Dict[str, Any]:
    """
    Get memory statistics for debugging/dashboard
    """
    try:
        session_size = get_session_memory_size(uuid)
        limit = get_session_memory_limit()
        
        # Get persistent memory info
        from memory.persistent_memory import get_summary
        persistent_summary = get_summary(uuid)
        persistent_size = len(persistent_summary) if persistent_summary else 0
        
        return {
            "session_memory_chars": session_size,
            "session_memory_limit": limit,
            "session_memory_usage_percent": (session_size / limit * 100) if limit > 0 else 0,
            "persistent_memory_chars": persistent_size,
            "has_persistent_memory": persistent_summary is not None
        }
    except Exception as e:
        print(f"❌ Error getting memory stats: {e}")
        return {}

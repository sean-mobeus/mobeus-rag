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
    """Log summarization events for dashboard visibility - now to both file AND database"""
    
    # File logging (keep existing behavior)
    with open("summarization_events.jsonl", "a") as f:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "user_uuid": uuid,
            "event_type": event_type,
            "details": details or {}
        }
        f.write(json.dumps(entry) + "\n")
    
    # ADD database logging
    def _log_to_db():
        with get_connection() as conn:
            with conn.cursor() as cur:
                details_dict = details or {}
                cur.execute("""
                    INSERT INTO summarization_events 
                    (uuid, event_type, trigger_reason, conversation_length, 
                     summary_generated, chars_before, chars_after, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    uuid,
                    event_type,
                    details_dict.get('trigger_reason', event_type),
                    details_dict.get('conversation_length', 0),
                    details_dict.get('summary', ''),
                    details_dict.get('chars_before', 0),
                    details_dict.get('chars_after', 0),
                    json.dumps(details_dict)
                ))
                conn.commit()
    
    execute_db_operation(_log_to_db)

def store_session_prompt(user_uuid: str, prompt_data: dict):
    """Store the actual prompt used for a session"""
    def _store_impl():
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO session_prompts 
                    (uuid, system_prompt, persistent_summary, session_context, 
                     final_prompt, prompt_length, estimated_tokens, strategy, model)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user_uuid,
                    prompt_data.get('system_prompt', ''),
                    prompt_data.get('persistent_summary', ''),
                    prompt_data.get('session_context', ''),
                    prompt_data.get('final_prompt', ''),
                    prompt_data.get('prompt_length', 0),
                    prompt_data.get('estimated_tokens', 0),
                    prompt_data.get('strategy', 'auto'),
                    prompt_data.get('model', '')
                ))
                conn.commit()
    
    execute_db_operation(_store_impl)
    print(f"✅ Stored prompt data for session {user_uuid}")


def summarize_and_archive_session(uuid: str, reason: str = "auto_limit"):
    """
    Summarize current session memory and move it to persistent memory
    NOW WITH COMPLETE DATA PRESERVATION
    """
    try:
        # STEP 1: Store complete session snapshot BEFORE summarization
        print(f"📸 STORING SESSION SNAPSHOT before summarization for {uuid}")
        interactions_stored = store_session_snapshot_before_summarization(uuid, reason)
        
        # STEP 2: Get conversation text for summarization
        conversation_text = format_conversation_for_summary(uuid)
        chars_before = len(conversation_text)
        print(f"📝 CONVERSATION LENGTH: {chars_before} chars")
        
        if not conversation_text.strip():
            print(f"⚠️ No conversation to summarize for {uuid}")
            return
        
        print(f"📝 GENERATING SUMMARY for {uuid}...")
        # STEP 3: Generate summary using OpenAI
        summary = generate_conversation_summary(conversation_text)
        print(f"📝 SUMMARY GENERATED: {len(summary) if summary else 0} chars")
        
        if summary:
            # STEP 4: Store summary in persistent memory
            from memory.persistent_memory import append_to_summary
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            summary_with_timestamp = f"[{timestamp}] {summary}"
            print(f"📝 STORING SUMMARY in persistent memory for {uuid}")
            append_to_summary(uuid, summary_with_timestamp)
            
            # STEP 5: LOG THE EVENT WITH COMPLETE DATA
            log_summarization_event(uuid, reason, {
                "conversation_length": chars_before,
                "summary_length": len(summary),
                "summary": summary,  # STORE ACTUAL SUMMARY
                "chars_before": chars_before,
                "chars_after": 0,
                "interactions_preserved": interactions_stored,
                "timestamp": timestamp,
                "trigger_reason": reason
            })
            
            # STEP 6: Clear session memory (now that everything is preserved)
            print(f"📝 CLEARING SESSION MEMORY for {uuid}")
            clear_session_memory(uuid)
            
            print(f"✅ Session memory summarized and archived for {uuid}")
            return True
        else:
            print(f"⚠️ Failed to generate summary for {uuid}")
            return False
            
    except Exception as e:
        print(f"❌ Error summarizing session for {uuid}: {e}")
        import traceback
        traceback.print_exc()
        return False

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
    
def force_session_summary(uuid: str, reason: str = "user_requested"):
    """
    Force summarization with comprehensive logging and validation
    """
    try:
        print(f"🤖 FORCE SUMMARIZATION: Starting for {uuid} - reason: {reason}")
        
        # Check if there's anything to summarize
        current_size = get_session_memory_size(uuid)
        print(f"📊 CURRENT SESSION SIZE: {current_size} chars")
        
        if current_size > 100:  # Only summarize if substantial content
            print(f"📝 FORCING SUMMARIZATION ({reason}) for {uuid}")
            summarize_and_archive_session(uuid, reason)
            
            # Verify it worked
            final_size = get_session_memory_size(uuid)
            print(f"📊 FINAL SESSION SIZE: {final_size} chars")
            
            if final_size == 0:
                print(f"✅ FORCE SUMMARIZATION SUCCESS for {uuid}")
                return True
            else:
                print(f"⚠️ FORCE SUMMARIZATION INCOMPLETE for {uuid}")
                return False
        else:
            print(f"⏭️ SKIPPING SUMMARIZATION: Too little content ({current_size} chars)")
            return False
            
    except Exception as e:
        print(f"❌ FORCE SUMMARIZATION FAILED for {uuid}: {e}")
        import traceback
        traceback.print_exc()
        return False

def store_session_snapshot_before_summarization(uuid: str, reason: str):
    """
    Store complete session data BEFORE summarization for historical analysis
    This preserves the conversation data that would otherwise be lost
    """
    try:
        # Get all current session data
        conversation = get_all_session_memory(uuid)
        if not conversation:
            print(f"⚠️ No conversation to snapshot for {uuid}")
            return
            
        # Store each interaction in interaction_logs for historical analysis
        from datetime import datetime
        snapshot_time = datetime.now()
        
        def _store_snapshot():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Create pairs of user->assistant interactions
                    current_user_msg = None
                    interaction_count = 0
                    
                    for msg in conversation:
                        if msg["role"] == "user":
                            current_user_msg = msg["message"]
                        elif msg["role"] == "assistant" and current_user_msg:
                            interaction_count += 1
                            interaction_id = f"{uuid}_snapshot_{snapshot_time.strftime('%Y%m%d_%H%M%S')}_{interaction_count}"
                            
                            cur.execute("""
                                INSERT INTO interaction_logs 
                                (uuid, interaction_id, created_at, user_message, assistant_response, 
                                 rag_context, strategy, model, tools_called)
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                uuid,
                                interaction_id,
                                msg.get("created_at", snapshot_time),
                                current_user_msg,
                                msg["message"],
                                f"Pre-summarization snapshot - {reason}",
                                "historical_data",
                                runtime_config.get("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17"),
                                "Historical snapshot - no tool data"
                            ))
                            current_user_msg = None
                    
                    conn.commit()
                    print(f"✅ Stored {interaction_count} interactions as historical snapshot for {uuid}")
                    return interaction_count
        
        return execute_db_operation(_store_snapshot)
        
    except Exception as e:
        print(f"❌ Error storing session snapshot: {e}")
        import traceback
        traceback.print_exc()
        return 0
# session_dashboard.py - FIXED VERSION
import os
import json
import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Query, Path
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from memory.session_memory import get_all_session_memory, get_memory_stats
from memory.persistent_memory import append_to_summary, get_summary
from memory.db import get_connection, execute_db_operation
from pydantic import BaseModel
import runtime_config
from config import LOG_DIR

router = APIRouter()

# Token pricing (you can make these configurable later)
TOKEN_PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},  # per 1K tokens
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
    "gpt-4o-realtime-preview-2024-12-17": {"input": 0.005, "output": 0.02}  # Realtime pricing
}

def get_session_historical_stats(uuid: str) -> Dict[str, Any]:
    """Get comprehensive historical session statistics from database"""
    try:
        def _get_historical_stats():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Get total messages from session_memory AND interaction_logs
                    cur.execute("""
                        SELECT 
                            -- Current session memory
                            (SELECT COUNT(*) FROM session_memory WHERE uuid = %s) as current_messages,
                            (SELECT COUNT(CASE WHEN role = 'user' THEN 1 END) FROM session_memory WHERE uuid = %s) as current_user_messages,
                            (SELECT COUNT(CASE WHEN role = 'assistant' THEN 1 END) FROM session_memory WHERE uuid = %s) as current_assistant_messages,
                            
                            -- Historical interaction logs
                            (SELECT COUNT(*) FROM interaction_logs WHERE uuid = %s) as historical_interactions,
                            
                            -- Session timing
                            (SELECT MIN(created_at) FROM session_memory WHERE uuid = %s) as first_current_message,
                            (SELECT MAX(created_at) FROM session_memory WHERE uuid = %s) as last_current_message,
                            (SELECT MIN(created_at) FROM interaction_logs WHERE uuid = %s) as first_historical_message,
                            (SELECT MAX(created_at) FROM interaction_logs WHERE uuid = %s) as last_historical_message
                    """, (uuid, uuid, uuid, uuid, uuid, uuid, uuid, uuid))
                    
                    row = cur.fetchone()
                    if not row:
                        return {}
                    
                    (current_messages, current_user_messages, current_assistant_messages, 
                     historical_interactions, first_current, last_current, 
                     first_historical, last_historical) = row
                    
                    # Calculate totals
                    total_messages = (current_messages or 0) + (historical_interactions or 0) * 2  # Each interaction = user + assistant
                    total_user_messages = (current_user_messages or 0) + (historical_interactions or 0)
                    total_assistant_messages = (current_assistant_messages or 0) + (historical_interactions or 0)
                    
                    # Calculate session duration
                    first_message = min(filter(None, [first_current, first_historical]), default=None)
                    last_message = max(filter(None, [last_current, last_historical]), default=None)
                    
                    duration = 0
                    if first_message and last_message:
                        duration = (last_message - first_message).total_seconds() / 60
                    
                    return {
                        "total_messages": total_messages,
                        "user_messages": total_user_messages,
                        "assistant_messages": total_assistant_messages,
                        "historical_interactions": historical_interactions or 0,
                        "current_messages": current_messages or 0,
                        "first_message": first_message.isoformat() if first_message else None,
                        "last_message": last_message.isoformat() if last_message else None,
                        "session_duration": round(duration, 1),
                        "avg_message_length": 0  # Calculate separately if needed
                    }
        
        return execute_db_operation(_get_historical_stats)
        return result if isinstance(result, dict) else {}
    except Exception as e:
        print(f"Error getting historical stats for {uuid}: {e}")
        return {}

def calculate_session_cost_from_db(uuid: str) -> Dict[str, Any]:
    """Calculate session cost from actual stored data"""
    try:
        def _get_cost_data():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Get all messages for this session (current + historical)
                    cur.execute("""
                        SELECT message FROM session_memory WHERE uuid = %s
                        UNION ALL
                        SELECT user_message FROM interaction_logs WHERE uuid = %s AND user_message IS NOT NULL
                        UNION ALL  
                        SELECT assistant_response FROM interaction_logs WHERE uuid = %s AND assistant_response IS NOT NULL
                    """, (uuid, uuid, uuid))
                    
                    messages = cur.fetchall()
                    return [row[0] for row in messages if row[0]]
        
        all_messages = execute_db_operation(_get_cost_data) or []
        
        # Calculate tokens and cost
        total_input_tokens = 0
        total_output_tokens = 0
        
        for i, message in enumerate(all_messages):
            tokens = len(message) // 4  # Rough estimate
            if i % 2 == 0:  # Assume even indices are user messages
                total_input_tokens += tokens
            else:  # Odd indices are assistant messages  
                total_output_tokens += tokens
        
        # Use current realtime model pricing
        realtime_model = runtime_config.get("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
        pricing = TOKEN_PRICING.get(realtime_model, {"input": 0.005, "output": 0.020})
        
        input_cost = (total_input_tokens / 1000) * pricing["input"]
        output_cost = (total_output_tokens / 1000) * pricing["output"]
        total_cost = input_cost + output_cost
        
        return {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "total_tokens": total_input_tokens + total_output_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost,
            "model_used": realtime_model
        }
        
    except Exception as e:
        print(f"Error calculating cost for {uuid}: {e}")
        return {
            "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            "input_cost": 0.0, "output_cost": 0.0, "total_cost": 0.0,
            "model_used": "unknown"
        }

def get_recent_summarization_events(uuid: str) -> list:
    """Get recent summarization events for dashboard - DATABASE FIRST, file fallback"""
    events = []
    
    # TRY DATABASE FIRST
    try:
        def _get_from_db():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT event_type, created_at, trigger_reason, conversation_length,
                               summary_generated, chars_before, chars_after
                        FROM summarization_events
                        WHERE uuid = %s
                        ORDER BY created_at DESC
                        LIMIT 10
                    """, (uuid,))
                    
                    db_events = []
                    for row in cur.fetchall():
                        event_type, created_at, trigger_reason, conv_len, summary, chars_before, chars_after = row
                        
                        event = {
                            "event_type": event_type,
                            "timestamp": created_at.isoformat() if created_at else "",
                            "user_uuid": uuid,
                            "details": {
                                "conversation_length": conv_len or 0,
                                "summary": summary or "",
                                "chars_before": chars_before or 0,
                                "chars_after": chars_after or 0,
                                "trigger_reason": trigger_reason or event_type
                            }
                        }
                        db_events.append(event)
                    
                    return db_events
        
        events = execute_db_operation(_get_from_db)
        if events:
            print(f"✅ Got {len(events)} summarization events from DATABASE for {uuid}")
            return events
            
    except Exception as e:
        print(f"⚠️ Database read failed for summarization events: {e}")
    
    # FALLBACK TO FILE (original code)
    try:
        summarization_log = os.path.join(LOG_DIR, os.getenv("MOBEUS_SUMMARIZATION_LOG", "summarization_events.jsonl"))
        if os.path.exists(summarization_log):
            with open(summarization_log, "r") as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        if event.get("user_uuid") == uuid:
                            events.append(event)
                    except:
                        continue
            print(f"📁 Got {len(events)} summarization events from FILE for {uuid}")
    except:
        pass
    
    return events[-10:]  # Last 10 events

def get_active_sessions(limit: int = 100):
    """Get ALL user sessions with proper historical data integration"""
    try:
        def _impl():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Get ALL sessions with proper historical data
                    cur.execute("""
                        WITH session_stats AS (
                            SELECT 
                                uuid,
                                MAX(created_at) as last_interaction,
                                COUNT(*) as current_messages,
                                MIN(created_at) as first_interaction
                            FROM session_memory
                            GROUP BY uuid
                        ),
                        historical_stats AS (
                            SELECT 
                                uuid,
                                MAX(created_at) as last_historical_interaction,
                                COUNT(*) as historical_interactions
                            FROM interaction_logs
                            GROUP BY uuid  
                        ),
                        persistent_sessions AS (
                            SELECT DISTINCT uuid, updated_at
                            FROM persistent_memory
                            WHERE uuid NOT IN (SELECT uuid FROM session_stats)
                        )
                        
                        SELECT 
                            COALESCE(s.uuid, h.uuid, p.uuid) as uuid,
                            GREATEST(
                                COALESCE(s.last_interaction, '1970-01-01'::timestamp),
                                COALESCE(h.last_historical_interaction, '1970-01-01'::timestamp),
                                COALESCE(p.updated_at, '1970-01-01'::timestamp)
                            ) as last_interaction,
                            COALESCE(s.current_messages, 0) as current_messages,
                            COALESCE(h.historical_interactions, 0) as historical_interactions,
                            s.first_interaction
                        FROM session_stats s
                        FULL OUTER JOIN historical_stats h ON s.uuid = h.uuid
                        FULL OUTER JOIN persistent_sessions p ON COALESCE(s.uuid, h.uuid) = p.uuid
                        ORDER BY last_interaction DESC
                        LIMIT %s
                    """, (limit,))
                    
                    sessions = []
                    for row in cur.fetchall():
                        uuid, last_interaction, current_messages, historical_interactions, first_interaction = row
                        
                        # Calculate total messages 
                        total_messages = (current_messages or 0) + (historical_interactions or 0) * 2
                        
                        # Get session summary
                        summary = get_summary(uuid) or ""
                        
                        # Calculate cost using our improved function
                        cost_data = calculate_session_cost_from_db(uuid)
                        
                        # Determine status
                        status = "active" if current_messages > 0 else "summarized"
                        
                        sessions.append({
                            "uuid": uuid,
                            "last_interaction": last_interaction.isoformat() if last_interaction else None,
                            "message_count": total_messages,
                            "user_messages": total_messages // 2,  # Approximate
                            "assistant_messages": total_messages // 2,  # Approximate
                            "summary": summary[:100] + "..." if len(summary) > 100 else summary,
                            "status": status,
                            "cost_estimate": cost_data.get("total_cost", 0.0),
                            "current_messages": current_messages or 0,
                            "historical_interactions": historical_interactions or 0
                        })
                    
                    return sessions
        
        return execute_db_operation(_impl)
    except Exception as e:
        print(f"Error getting sessions: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_comprehensive_final_prompt(uuid: str) -> Dict[str, Any]:
    """Get the complete, actual final prompt used for this session"""
    try:
        def _get_latest_prompt():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            system_prompt, persistent_summary, session_context,
                            final_prompt, prompt_length, estimated_tokens,
                            strategy, model, created_at
                        FROM session_prompts
                        WHERE uuid = %s
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (uuid,))
                    
                    row = cur.fetchone()
                    if row:
                        (system_prompt, persistent_summary, session_context, 
                         final_prompt, prompt_length, estimated_tokens,
                         strategy, model, created_at) = row
                        
                        return {
                            "final_prompt": "No prompt data available for this session",
                            "source": "NOT_AVAILABLE",
                            "system_prompt": "",
                            "persistent_summary": "",
                            "session_context": "",
                            "prompt_length": 0,
                            "estimated_tokens": 0,
                            "strategy": "auto",
                            "model": "unknown",
                            "timestamp": ""
                        }
                    return {}
        
        db_result = execute_db_operation(_get_latest_prompt)
        if db_result:
            return db_result
            
    except Exception as e:
        print(f"Error getting comprehensive prompt for {uuid}: {e}")
    
    return {
        "final_prompt": "No prompt data available for this session",
        "source": "NOT_AVAILABLE"
    }

def get_session_deep_dive(uuid: str):
    """Get comprehensive session analysis with FIXED data persistence"""
    try:
        # Get conversation data
        conversation = get_all_session_memory(uuid)
        summary = get_summary(uuid)
        memory_stats = get_memory_stats(uuid)
        
        # FIXED: Ensure these functions return dicts, not None/strings
        stats = get_session_historical_stats(uuid)
        if not isinstance(stats, dict):
            stats = {}
        
        cost_analysis = calculate_session_cost_from_db(uuid)
        if not isinstance(cost_analysis, dict):
            cost_analysis = {}
        
        # Get current config
        current_config = {
            "system_prompt": runtime_config.get("SYSTEM_PROMPT", ""),
            "tone_style": runtime_config.get("TONE_STYLE", "empathetic"),
            "temperature": runtime_config.get("TEMPERATURE", 0.7),
            "model": runtime_config.get("GPT_MODEL", "gpt-4"),
            "realtime_model": runtime_config.get("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17"),
            "session_memory_limit": runtime_config.get("SESSION_MEMORY_CHAR_LIMIT", 15000),
            "rag_enabled": runtime_config.get("RAG_ENABLED", True)
        }
        
        # FIXED: Ensure prompt_construction is always a dict
        prompt_construction = get_comprehensive_final_prompt(uuid)
        if not isinstance(prompt_construction, dict):
            prompt_construction = {"final_prompt": "No prompt data available", "source": "NOT_AVAILABLE"}
        
        # Get summarization events
        summarization_events = get_recent_summarization_events(uuid)
        if not isinstance(summarization_events, list):
            summarization_events = []
        
        # Memory transitions analysis (simplified)
        memory_transitions = []
        if len(summarization_events) > 0:
            for i, event in enumerate(summarization_events):
                if isinstance(event, dict):
                    memory_transitions.append({
                        "cycle_number": i + 1,
                        "trigger": event.get("details", {}).get("trigger_reason", "auto"),
                        "timestamp": event.get("timestamp", ""),
                        "chars_processed": event.get("details", {}).get("conversation_length", 0)
                    })
        
        return {
            "uuid": uuid,
            "conversation": conversation,
            "summary": summary,
            "stats": stats,
            "memory_stats": memory_stats,
            "memory_transitions": memory_transitions,
            "prompt_construction": prompt_construction,
            "cost_analysis": cost_analysis,
            "session_config": current_config,
            "summarization_events": summarization_events
        }
        
    except Exception as e:
        print(f"Error getting session deep dive: {e}")
        import traceback
        traceback.print_exc()
        return {"uuid": uuid, "error": str(e)}

class SummaryUpdate(BaseModel):
    summary: str

@router.post("/sessions/{uuid}/summary")
async def update_session_summary(uuid: str, data: SummaryUpdate):
    """Update the session summary."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    summary_with_timestamp = f"[{timestamp}] Manual Update: {data.summary}"
    
    try:
        append_to_summary(uuid, summary_with_timestamp)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@router.get("/sessions/{uuid}/deep-dive", response_class=HTMLResponse)
async def session_deep_dive(
    request: Request,
    uuid: str = Path(..., description="Session UUID")
):
    """Enhanced session view with FIXED UI and data persistence"""
    print(f"🔍 Deep dive requested for UUID: {uuid}")
    
    session: Dict[str, Any] = get_session_deep_dive(uuid)
    session = session if isinstance(session, dict) else {}
    session_json = json.dumps(session, default=str)
    
    # Safely extract values with improved error handling
    stats = session.get('stats', {})
    cost_analysis = session.get('cost_analysis', {})
    memory_stats = session.get('memory_stats', {})
    session_config = session.get('session_config', {})
    prompt_construction = session.get('prompt_construction', {})
    conversation = session.get('conversation', [])
    memory_transitions = session.get('memory_transitions', [])
    summary = session.get('summary', '')
    summarization_events = session.get('summarization_events', [])

    # FIXED: Extract values with proper defaults
    total_messages = stats.get('total_messages', 0)
    total_tokens = cost_analysis.get('total_tokens', 0)
    total_cost = cost_analysis.get('total_cost', 0)
    session_duration = stats.get('session_duration', 0)
    current_chars = memory_stats.get('session_memory_chars', 0)
    memory_cycles = len(memory_transitions)
    
    # Extract cost analysis values
    input_tokens = cost_analysis.get('input_tokens', 0)
    output_tokens = cost_analysis.get('output_tokens', 0)
    input_cost = cost_analysis.get('input_cost', 0)
    output_cost = cost_analysis.get('output_cost', 0)
    model_used = cost_analysis.get('model_used', 'Unknown')
    
    # Memory values
    session_memory_limit = memory_stats.get('session_memory_limit', 15000)
    summary_length = len(summary) if summary else 0
    summary_status = 'Active' if summary else 'Empty'
    
    # FIXED: Improved summarization events HTML with cleaner UI
    summarization_events_html = ""
    if summarization_events:
        for i, event in enumerate(summarization_events):
            event_type = event.get("event_type", "unknown").replace("_", " ").title()
            timestamp = event.get("timestamp", "")
            details = event.get("details", {})
            
            conversation_length = details.get("conversation_length", "Unknown")
            actual_summary = details.get("summary", "No summary available")
            trigger_reason = details.get("trigger_reason", event_type)
            
            # Truncate summary for display
            summary_preview = actual_summary[:150] + "..." if len(actual_summary) > 150 else actual_summary
            
            summarization_events_html += f'''
            <div class="summarization-event" style="margin-bottom: 1rem; border: 1px solid var(--border-color); border-radius: 0.5rem; overflow: hidden;">
                <div class="event-header" style="background: var(--code-bg); padding: 0.75rem; border-bottom: 1px solid var(--border-color);">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <strong style="color: var(--accent-color);">{trigger_reason}</strong>
                            <span style="margin-left: 1rem; font-size: 0.875rem; opacity: 0.7;">{timestamp.split('T')[0] if 'T' in timestamp else timestamp}</span>
                        </div>
                        <button class="summary-analyze-btn" onclick="showSummaryDetails({i})" 
                                style="background: var(--accent-color); color: var(--background-color); border: none; padding: 0.375rem 0.75rem; border-radius: 0.375rem; cursor: pointer; font-size: 0.75rem;">
                            🔍 View Summary
                        </button>
                    </div>
                    <div style="font-size: 0.8rem; margin-top: 0.5rem; opacity: 0.8;">
                        Processed: {conversation_length} chars
                    </div>
                </div>
                <div class="event-preview" style="padding: 0.75rem; font-size: 0.875rem; background: rgba(0,0,0,0.2);">
                    {summary_preview}
                </div>
                <div id="summary-details-{i}" class="summary-details" style="display: none; padding: 1rem; background: var(--code-bg); border-top: 1px solid var(--border-color); max-height: 300px; overflow-y: auto;">
                    <div style="font-family: 'Courier New', monospace; font-size: 0.875rem; line-height: 1.5; white-space: pre-wrap;">{actual_summary}</div>
                </div>
            </div>
            '''
    else:
        summarization_events_html = '''
        <div class="summarization-event" style="padding: 1.5rem; text-align: center; opacity: 0.7; border: 1px dashed var(--border-color); border-radius: 0.5rem;">
            <strong>No Summarization Events</strong><br>
            <small>No summaries have been generated for this session yet.</small>
        </div>
        '''
    
    # Generate conversation HTML with proper JavaScript escaping
    conversation_html = ""
    for i, interaction in enumerate((conversation or [])[-15:]):  # Last 15 messages
        if isinstance(interaction, dict):
            role = interaction.get("role", "")
            message = interaction.get("message", "")
            created_at = interaction.get("created_at", "")
        else:
            role = ""
            message = str(interaction)
            created_at = ""
    
        message_preview = message[:300] + ('...' if len(message) > 300 else '')
    
        # FIXED: Properly escape message for JavaScript
        analyze_button = ""
        if role == "assistant":
            # Properly escape the message for JavaScript
            escaped_message = json.dumps(message[:500])  # JSON encoding handles all escaping
            analyze_button = f'''
            <div style="margin-top: 0.5rem;">
                <button class="analyze-btn" onclick="analyzeMessage({i}, {escaped_message})">
                    🔍 Analyze Response
                </button>
            </div>
            '''
    
        conversation_html += f'''
        <div class="message {role}" style="margin-bottom: 1rem; padding: 1rem; border-radius: 0.5rem; {'border-left: 4px solid var(--primary-color);' if role == 'user' else 'border-left: 4px solid var(--accent-color);'} background: {'rgba(37, 99, 235, 0.1)' if role == 'user' else 'rgba(6, 214, 160, 0.1)'};">
            <div class="message-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; font-size: 0.875rem; opacity: 0.8;">
                <span style="font-weight: 600;">{role.title()}</span>
                <span>{created_at}</span>
            </div>
            <div class="message-content" style="font-size: 0.9rem; line-height: 1.4;">{message_preview}</div>
            {analyze_button}
        </div>
        '''

    # Add final prompt section
    final_prompt_section = ""
    if prompt_construction.get("final_prompt"):
        final_prompt = prompt_construction["final_prompt"]
        prompt_length = len(final_prompt)
        estimated_tokens = prompt_construction.get("estimated_tokens", prompt_length // 4)
        
        final_prompt_section = f'''
        <div class="card">
            <div class="card-header">
                <span class="card-icon">📜</span>
                <span class="card-title">Final Prompt Sent to OpenAI</span>
                <span style="font-size: 0.875rem; color: var(--accent-color);">
                    {prompt_length:,} chars | ~{estimated_tokens:,} tokens
                </span>
            </div>
            <div class="card-body">
                <div style="background: var(--code-bg); border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1rem; max-height: 400px; overflow-y: auto;">
                    <pre style="margin: 0; font-family: 'Courier New', monospace; font-size: 0.8rem; line-height: 1.4; white-space: pre-wrap; color: var(--matrix-green);">{final_prompt}</pre>
                </div>
                <div style="margin-top: 1rem; padding: 0.75rem; background: rgba(6, 214, 160, 0.1); border: 1px solid var(--accent-color); border-radius: 0.375rem;">
                    <strong style="color: var(--accent-color);">Source:</strong> {prompt_construction.get("source", "Unknown")} | 
                    <strong style="color: var(--accent-color);">Strategy:</strong> {prompt_construction.get("strategy", "auto")} |
                    <strong style="color: var(--accent-color);">Model:</strong> {prompt_construction.get("model", "unknown")}
                </div>
            </div>
        </div>
        '''

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mobeus Assistant — Session Deep Dive</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@3.7.1/dist/chart.min.js"></script>
        <style>
            :root {{
                --primary-color: #2563eb;
                --primary-light: rgba(37, 99, 235, 0.1);
                --secondary-color: #1e40af;
                --background-color: #0f172a;
                --card-color: #1e293b;
                --text-color: #f1f5f9;
                --border-color: #334155;
                --accent-color: #06d6a0;
                --warning-color: #ffd60a;
                --danger-color: #ef476f;
                --matrix-green: #00ff41;
                --code-bg: #0f1629;
            }}
            
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            
            body {{
                font-family: 'Courier New', monospace;
                background: linear-gradient(135deg, var(--background-color) 0%, #1a202c 100%);
                color: var(--text-color);
                line-height: 1.5;
                min-height: 100vh;
            }}
            
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                padding: 1.5rem;
            }}
            
            .breadcrumb {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 0.875rem;
                margin-bottom: 1rem;
                color: var(--accent-color);
            }}
            
            .breadcrumb a {{
                color: var(--accent-color);
                text-decoration: none;
            }}
            
            .breadcrumb span {{
                color: var(--text-color);
                opacity: 0.6;
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 2rem;
                padding: 2rem;
                background: linear-gradient(135deg, var(--card-color) 0%, rgba(30, 41, 59, 0.8) 100%);
                border-radius: 1rem;
                border: 1px solid var(--border-color);
                box-shadow: 0 0 20px rgba(0, 255, 65, 0.2);
            }}
            
            .header h1 {{
                font-size: 2.5rem;
                font-weight: bold;
                background: linear-gradient(135deg, var(--matrix-green), var(--accent-color));
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
                margin-bottom: 0.5rem;
                text-shadow: 0 0 10px rgba(0, 255, 65, 0.5);
            }}
            
            .header .session-id {{
                font-family: 'Courier New', monospace;
                color: var(--accent-color);
                font-size: 1rem;
                letter-spacing: 2px;
            }}
            
            .grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 1.5rem;
                margin-bottom: 2rem;
            }}
            
            .card {{
                background: linear-gradient(135deg, var(--card-color) 0%, rgba(30, 41, 59, 0.8) 100%);
                border-radius: 1rem;
                padding: 1.5rem;
                border: 1px solid var(--border-color);
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
                transition: all 0.3s ease;
                margin-bottom: 1.5rem;
            }}
            
            .card:hover {{
                box-shadow: 0 0 20px rgba(0, 255, 65, 0.3);
                transform: translateY(-2px);
            }}
            
            .card-header {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                margin-bottom: 1rem;
                padding-bottom: 0.5rem;
                border-bottom: 1px solid var(--border-color);
            }}
            
            .card-title {{
                font-size: 1.25rem;
                font-weight: bold;
                color: var(--matrix-green);
            }}
            
            .card-icon {{
                color: var(--accent-color);
            }}
            
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
                gap: 1rem;
                margin-bottom: 1.5rem;
            }}
            
            .metric {{
                text-align: center;
                padding: 1rem;
                background: var(--code-bg);
                border-radius: 0.5rem;
                border: 1px solid var(--border-color);
            }}
            
            .metric-value {{
                font-size: 1.5rem;
                font-weight: bold;
                color: var(--matrix-green);
                margin-bottom: 0.25rem;
            }}
            
            .metric-label {{
                font-size: 0.75rem;
                color: var(--text-color);
                opacity: 0.8;
                text-transform: uppercase;
                letter-spacing: 1px;
            }}
            
            .conversation-flow {{
                max-height: 600px;
                overflow-y: auto;
            }}
            
            .analyze-btn, .summary-analyze-btn {{
                background: linear-gradient(135deg, var(--accent-color), var(--matrix-green));
                border: none;
                color: var(--background-color);
                padding: 0.375rem 0.75rem;
                border-radius: 0.375rem;
                font-size: 0.75rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.3s ease;
                font-family: inherit;
            }}
            
            .analyze-btn:hover, .summary-analyze-btn:hover {{
                transform: scale(1.05);
                box-shadow: 0 0 15px rgba(0, 255, 65, 0.5);
            }}
            
            .analyze-modal {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.8);
                display: none;
                z-index: 1000;
                justify-content: center;
                align-items: center;
            }}
            
            .analyze-content {{
                background: var(--card-color);
                border-radius: 1rem;
                padding: 2rem;
                max-width: 900px;
                max-height: 90vh;
                overflow-y: auto;
                border: 1px solid var(--border-color);
                box-shadow: 0 0 30px rgba(0, 255, 65, 0.3);
            }}
            
            .cost-breakdown {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
                gap: 1rem;
            }}
            
            .cost-item {{
                text-align: center;
                padding: 0.75rem;
                background: var(--code-bg);
                border-radius: 0.5rem;
                border: 1px solid var(--border-color);
            }}
            
            .cost-value {{
                font-size: 1.25rem;
                font-weight: bold;
                color: var(--warning-color);
                margin-bottom: 0.25rem;
            }}
            
            .cost-label {{
                font-size: 0.75rem;
                opacity: 0.8;
                text-transform: uppercase;
            }}
            
            @media (max-width: 768px) {{
                .grid {{
                    grid-template-columns: 1fr;
                }}
                
                .metrics-grid {{
                    grid-template-columns: repeat(2, 1fr);
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="breadcrumb">
                <a href="/admin/">Dashboard</a>
                <span>/</span>
                <a href="/admin/sessions">Sessions</a>
                <span>/</span>
                <span>Deep Dive</span>
            </div>
            
            <div class="header">
                <h1>🌐 SESSION DEEP DIVE</h1>
                <div class="session-id">UUID: {session.get('uuid', 'Unknown')}</div>
            </div>
            
            <!-- Overview Metrics -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">📊</span>
                    <span class="card-title">Session Matrix (FIXED - With Historical Data)</span>
                </div>
                <div class="metrics-grid">
                    <div class="metric">
                        <div class="metric-value">{total_messages}</div>
                        <div class="metric-label">Total Messages</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{total_tokens:,}</div>
                        <div class="metric-label">Total Tokens</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">${total_cost:.4f}</div>
                        <div class="metric-label">Est. Cost</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{session_duration}</div>
                        <div class="metric-label">Duration (min)</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{current_chars}</div>
                        <div class="metric-label">Memory Chars</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{memory_cycles}</div>
                        <div class="metric-label">Memory Cycles</div>
                    </div>
                </div>
            </div>
            
            <!-- Main Grid -->
            <div class="grid">
                <!-- Cost Analysis -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-icon">💰</span>
                        <span class="card-title">Cost Analysis (FIXED)</span>
                    </div>
                    <div class="cost-breakdown">
                        <div class="cost-item">
                            <div class="cost-value">{input_tokens:,}</div>
                            <div class="cost-label">Input Tokens</div>
                        </div>
                        <div class="cost-item">
                            <div class="cost-value">{output_tokens:,}</div>
                            <div class="cost-label">Output Tokens</div>
                        </div>
                        <div class="cost-item">
                            <div class="cost-value">${input_cost:.4f}</div>
                            <div class="cost-label">Input Cost</div>
                        </div>
                        <div class="cost-item">
                            <div class="cost-value">${output_cost:.4f}</div>
                            <div class="cost-label">Output Cost</div>
                        </div>
                    </div>
                    <div style="margin-top: 1rem; text-align: center; color: var(--accent-color);">
                        Model: {model_used}
                    </div>
                </div>
                
                <!-- Memory System Status -->
                <div class="card">
                    <div class="card-header">
                        <span class="card-icon">🧠</span>
                        <span class="card-title">Memory System</span>
                    </div>
                    <div style="display: flex; flex-direction: column; gap: 1rem;">
                        <div style="padding: 1rem; background: var(--code-bg); border-radius: 0.5rem; border-left: 4px solid var(--accent-color);">
                            <div style="font-weight: bold; color: var(--accent-color); margin-bottom: 0.5rem;">Session Memory</div>
                            <div>Characters: {current_chars:,} / {session_memory_limit:,}</div>
                            <div>Current Messages: {stats.get('current_messages', 0)}</div>
                        </div>
                        <div style="padding: 1rem; background: var(--code-bg); border-radius: 0.5rem; border-left: 4px solid var(--matrix-green);">
                            <div style="font-weight: bold; color: var(--matrix-green); margin-bottom: 0.5rem;">Persistent Memory</div>
                            <div>Summary Length: {summary_length:,}</div>
                            <div>Status: {summary_status}</div>
                        </div>
                        <div style="padding: 1rem; background: var(--code-bg); border-radius: 0.5rem; border-left: 4px solid var(--warning-color);">
                            <div style="font-weight: bold; color: var(--warning-color); margin-bottom: 0.5rem;">Historical Data</div>
                            <div>Archived Interactions: {stats.get('historical_interactions', 0)}</div>
                            <div>Total Messages: {total_messages}</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Summarization Events (FIXED UI) -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">📝</span>
                    <span class="card-title">Summarization Events (FIXED - Clean UI)</span>
                </div>
                <div style="max-height: 500px; overflow-y: auto;">
                    {summarization_events_html}
                </div>
            </div>
            
            <!-- Conversation Flow (FIXED) -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">💬</span>
                    <span class="card-title">Conversation Flow (FIXED)</span>
                </div>
                <div class="conversation-flow">
                    {conversation_html}
                </div>
            </div>
            
            <!-- Final Prompt Section (NEW) -->
            {final_prompt_section}
            
            <!-- Session Configuration -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">⚙️</span>
                    <span class="card-title">Active Configuration</span>
                </div>
                <div style="background: var(--code-bg); border: 1px solid var(--border-color); border-radius: 0.5rem; padding: 1rem; font-family: 'Courier New', monospace; font-size: 0.875rem; white-space: pre-wrap; overflow-x: auto; max-height: 300px; overflow-y: auto; color: var(--matrix-green);">{json.dumps(session_config, indent=2)}</div>
            </div>
        </div>
        
        <script>
            const sessionData = {session_json};
            
            // FIXED: Analyze message functionality with proper escaping
            function analyzeMessage(messageIndex, messageText) {{
                // Get session data for analysis
                const promptData = sessionData.prompt_construction || {{}};
                const conversationData = sessionData.conversation || [];
                
                let sessionMemory = "No session context";
                if (conversationData.length > 0) {{
                    const recentConversation = conversationData.slice(-10);
                    sessionMemory = recentConversation.map(msg => 
                        `${{msg.role}}: ${{msg.message}}`
                    ).join('\\n\\n');
                }}
                
                const persistentMemory = promptData.persistent_summary || 'No persistent memory';
                
                // Analyze message characteristics
                const wordCount = messageText.split(' ').length;
                const sentenceCount = messageText.split(/[.!?]+/).filter(s => s.trim().length > 0).length;
                const hasCodeBlocks = /```|`/.test(messageText);
                const hasLists = /^\\s*[-*•]\\s/m.test(messageText);
                const hasTechnicalTerms = /\\b(API|database|function|error|config|server|client|endpoint|JSON|HTTP|SQL)\\b/i.test(messageText);
                const hasQuestions = /\\?/.test(messageText);
                
                // Create modal
                let modal = document.getElementById('analyzeModal');
                if (!modal) {{
                    modal = document.createElement('div');
                    modal.id = 'analyzeModal';
                    modal.className = 'analyze-modal';
                    modal.onclick = function(e) {{
                        if (e.target === modal) closeAnalyzeModal();
                    }};
                    document.body.appendChild(modal);
                }}
                
                modal.innerHTML = `
                    <div class="analyze-content">
                        <h3 style="color: var(--matrix-green); margin-bottom: 1rem;">🔍 Assistant Response Analysis</h3>
                        
                        <div style="display: grid; gap: 1.5rem;">
                            <!-- Response Metrics -->
                            <div style="background: var(--code-bg); padding: 1rem; border-radius: 0.5rem; border-left: 4px solid var(--accent-color);">
                                <div style="font-weight: bold; color: var(--accent-color); margin-bottom: 0.5rem;">📊 Response Metrics</div>
                                <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; font-size: 0.875rem;">
                                    <div>Characters: <span style="color: var(--matrix-green);">${{messageText.length}}</span></div>
                                    <div>Words: <span style="color: var(--matrix-green);">${{wordCount}}</span></div>
                                    <div>Sentences: <span style="color: var(--matrix-green);">${{sentenceCount}}</span></div>
                                    <div>Est. Tokens: <span style="color: var(--matrix-green);">~${{Math.ceil(messageText.length / 4)}}</span></div>
                                </div>
                            </div>
                            
                            <!-- Response Characteristics -->
                            <div style="background: var(--code-bg); padding: 1rem; border-radius: 0.5rem; border-left: 4px solid var(--warning-color);">
                                <div style="font-weight: bold; color: var(--warning-color); margin-bottom: 0.5rem;">🎯 Response Characteristics</div>
                                <div style="font-size: 0.875rem; line-height: 1.6;">
                                    • Structure: ${{hasLists ? 'Lists/bullets' : 'Prose'}}<br>
                                    • Code blocks: ${{hasCodeBlocks ? 'Yes' : 'No'}}<br>
                                    • Technical content: ${{hasTechnicalTerms ? 'Yes' : 'No'}}<br>
                                    • Contains questions: ${{hasQuestions ? 'Yes' : 'No'}}
                                </div>
                            </div>
                            
                            <!-- Prompt Context -->
                            <div style="background: var(--code-bg); padding: 1rem; border-radius: 0.5rem; border-left: 4px solid var(--primary-color); max-height: 400px; overflow-y: auto;">
                                <div style="font-weight: bold; color: var(--primary-color); margin-bottom: 1rem;">🧠 Context Used</div>
                                
                                <div style="margin-bottom: 1rem;">
                                    <div style="font-weight: bold; color: var(--accent-color); margin-bottom: 0.5rem;">📚 Persistent Memory</div>
                                    <div style="background: rgba(0, 0, 0, 0.3); padding: 0.75rem; border-radius: 0.375rem; font-size: 0.8rem; max-height: 100px; overflow-y: auto; font-family: 'Courier New', monospace; white-space: pre-wrap;">
                                        ${{persistentMemory}}
                                    </div>
                                </div>
                                
                                <div style="margin-bottom: 1rem;">
                                    <div style="font-weight: bold; color: var(--warning-color); margin-bottom: 0.5rem;">💭 Session Memory</div>
                                    <div style="background: rgba(0, 0, 0, 0.3); padding: 0.75rem; border-radius: 0.375rem; font-size: 0.8rem; max-height: 100px; overflow-y: auto; font-family: 'Courier New', monospace; white-space: pre-wrap;">
                                        ${{sessionMemory}}
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <div style="text-align: center; margin-top: 1.5rem;">
                            <button onclick="closeAnalyzeModal()" style="background: var(--primary-color); color: white; border: none; padding: 0.5rem 1rem; border-radius: 0.375rem; cursor: pointer; font-weight: 500;">
                                Close Analysis
                            </button>
                        </div>
                    </div>
                `;
                
                modal.style.display = 'flex';
            }}

            function closeAnalyzeModal() {{
                const modal = document.getElementById('analyzeModal');
                if (modal) {{
                    modal.style.display = 'none';
                }}
            }}
            
            // FIXED: Summary details functionality
            function showSummaryDetails(eventIndex) {{
                const detailsDiv = document.getElementById(`summary-details-${{eventIndex}}`);
                if (detailsDiv) {{
                    if (detailsDiv.style.display === 'none') {{
                        detailsDiv.style.display = 'block';
                    }} else {{
                        detailsDiv.style.display = 'none';
                    }}
                }}
            }}
            
            console.log('✅ Session Deep Dive loaded with FIXED data persistence and UI');
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

@router.get("/sessions", response_class=HTMLResponse)
async def sessions_dashboard(
    request: Request,
    limit: int = Query(50, description="Number of sessions to show")
):
    """FIXED sessions dashboard with proper historical data"""
    
    sessions: List[Dict[str, Any]] = get_active_sessions(limit=limit)
    
    # Calculate aggregate stats with proper data
    total_sessions = len(sessions)
    total_messages = sum(session.get("message_count", 0) for session in sessions)
    total_cost = sum(session.get("cost_estimate", 0.0) for session in sessions)
    avg_messages = total_messages / total_sessions if total_sessions > 0 else 0
    
    now = datetime.datetime.now()
    active_today = sum(
        1 for session in sessions 
        if session.get("last_interaction") and 
        (now - datetime.datetime.fromisoformat(session["last_interaction"])).total_seconds() < 86400
    )
    
    # Generate table rows with enhanced data
    table_rows = []
    for session in sessions:
        uuid = session.get("uuid", "")
        last_interaction = session.get("last_interaction", "")
        message_count = session.get("message_count", 0)
        summary = session.get("summary", "")
        cost_estimate = session.get("cost_estimate", 0.0)
        status = session.get("status", "unknown")
        current_messages = session.get("current_messages", 0)
        historical_interactions = session.get("historical_interactions", 0)
        
        # Enhanced status display
        status_display = f"{status.title()}"
        if historical_interactions > 0:
            status_display += f" ({historical_interactions} archived)"
        
        badge_class = 'badge-active' if current_messages > 0 else 'badge-inactive'
        date_display = last_interaction.split("T")[0] if last_interaction else ""
        
        table_rows.append(f"""
        <tr>
            <td>
                <div class="truncate">{uuid}</div>
            </td>
            <td>
                {date_display}
                <span class="badge {badge_class}">{status_display}</span>
            </td>
            <td>
                <strong>{message_count}</strong>
                <br><small>Current: {current_messages} | Archive: {historical_interactions}</small>
            </td>
            <td>
                <strong>${cost_estimate:.4f}</strong>
            </td>
            <td>
                <div class="truncate">{summary}</div>
            </td>
            <td>
                <a href="/admin/sessions/{uuid}/deep-dive" style="color: #06d6a0; text-decoration: none; font-weight: 500;">🔍 Deep Dive</a>
            </td>
        </tr>
        """)
    
    # Convert data to JSON for JavaScript
    data_json = json.dumps({
        "sessions": sessions,
        "stats": {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "total_cost": total_cost,
            "avg_messages": avg_messages,
            "active_today": active_today
        }
    }, default=str)
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mobeus Assistant — Session Management Dashboard (FIXED)</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@3.7.1/dist/chart.min.js"></script>
        <style>
            :root {{
                --primary-color: #2563eb;
                --primary-light: rgba(37, 99, 235, 0.1);
                --secondary-color: #1e40af;
                --background-color: #f9fafb;
                --card-color: #ffffff;
                --text-color: #1f2937;
                --border-color: #e5e7eb;
                --good-color: #10b981;
                --warning-color: #f59e0b;
                --bad-color: #ef4444;
                --code-bg: #f3f4f6;
                --accent-color: #06d6a0;
            }}
            
            * {{
                box-sizing: border-box;
                margin: 0;
                padding: 0;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background-color: var(--background-color);
                color: var(--text-color);
                line-height: 1.5;
            }}
            
            .dashboard {{
                max-width: 1400px;
                margin: 0 auto;
                padding: 1.5rem;
            }}
            
            .breadcrumb {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                font-size: 0.875rem;
                margin-bottom: 1rem;
            }}
            
            .breadcrumb a {{
                color: var(--primary-color);
                text-decoration: none;
            }}
            
            .breadcrumb span {{
                color: #6b7280;
            }}
            
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1.5rem;
            }}
            
            h1, h2, h3 {{
                font-weight: 600;
            }}
            
            h1 {{
                font-size: 1.5rem;
            }}
            
            .card {{
                background-color: var(--card-color);
                border-radius: 0.5rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                overflow: hidden;
                margin-bottom: 1.5rem;
                border: 1px solid var(--border-color);
            }}
            
            .card-header {{
                padding: 1rem;
                border-bottom: 1px solid var(--border-color);
                font-weight: 600;
                display: flex;
                justify-content: space-between;
                align-items: center;
                background-color: #f9fafb;
            }}
            
            .card-body {{
                padding: 1rem;
            }}
            
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 1rem;
                margin-bottom: 1.5rem;
            }}
            
            .metric {{
                background-color: #f9fafb;
                border-radius: 0.5rem;
                padding: 1rem;
                text-align: center;
                border: 1px solid var(--border-color);
            }}
            
            .metric-value {{
                font-size: 1.5rem;
                font-weight: 600;
                margin-bottom: 0.25rem;
                color: var(--primary-color);
            }}
            
            .metric-label {{
                font-size: 0.75rem;
                color: #6b7280;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            
            .grid-layout {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 1.5rem;
            }}
            
            .chart-container {{
                height: 300px;
                margin-bottom: 1.5rem;
            }}
            
            .table-container {{
                overflow-x: auto;
            }}
            
            table {{
                width: 100%;
                border-collapse: collapse;
            }}
            
            th, td {{
                text-align: left;
                padding: 0.75rem 1rem;
                border-bottom: 1px solid var(--border-color);
            }}
            
            th {{
                background-color: #f9fafb;
                font-weight: 500;
                font-size: 0.875rem;
                color: #374151;
            }}
            
            tr:hover {{
                background-color: #f9fafb;
            }}
            
            .badge {{
                display: inline-block;
                padding: 0.25rem 0.5rem;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 500;
                margin-left: 0.5rem;
            }}
            
            .badge-active {{
                background-color: rgba(16, 185, 129, 0.1);
                color: #10b981;
            }}
            
            .badge-inactive {{
                background-color: rgba(107, 114, 128, 0.1);
                color: #6b7280;
            }}
            
            .truncate {{
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 250px;
            }}
            
            @media (max-width: 768px) {{
                .grid-layout {{
                    grid-template-columns: 1fr;
                }}
                
                .metrics-grid {{
                    grid-template-columns: repeat(2, 1fr);
                }}
            }}
        </style>
    </head>
    <body>
        <div class="dashboard">
            <div class="breadcrumb">
                <a href="/admin/">Dashboard</a>
                <span>/</span>
                <span>Sessions (FIXED - With Historical Data)</span>
            </div>
            
            <div class="header">
                <h1>🎯 Session Management Dashboard (FIXED)</h1>
            </div>
            
            <div class="card">
                <div class="card-header">
                    📊 Session Overview (FIXED - Includes Historical Data)
                </div>
                <div class="card-body">
                    <div class="metrics-grid">
                        <div class="metric">
                            <div class="metric-value">{total_sessions}</div>
                            <div class="metric-label">Total Sessions</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{active_today}</div>
                            <div class="metric-label">Active Today</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{total_messages:,}</div>
                            <div class="metric-label">Total Messages</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{avg_messages:.1f}</div>
                            <div class="metric-label">Avg Messages/Session</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">${total_cost:.4f}</div>
                            <div class="metric-label">Total Est. Cost</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    🔍 All Sessions (FIXED - Persistent Data)
                    <span>{total_sessions} sessions</span>
                </div>
                <div class="card-body">
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Session ID</th>
                                    <th>Last Activity</th>
                                    <th>Messages</th>
                                    <th>Est. Cost</th>
                                    <th>Summary</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {"".join(table_rows)}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            const dashboardData = {data_json};
            console.log('✅ Sessions Dashboard loaded with FIXED historical data integration');
            console.log('📊 Dashboard stats:', dashboardData.stats);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

# Update existing session_details route to redirect to deep dive
@router.get("/sessions/{uuid}", response_class=HTMLResponse)
async def session_details(request: Request, uuid: str = Path(...)):
    """Redirect to the enhanced deep dive view"""
    return RedirectResponse(url=f"/admin/sessions/{uuid}/deep-dive", status_code=302)
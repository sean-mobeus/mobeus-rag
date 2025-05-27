# session_dashboard.py
import os
import json
import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Query, Path
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from memory.session_memory import get_recent_interactions, get_memory_stats
from memory.persistent_memory import get_summary
from memory.db import get_connection, execute_db_operation
from pydantic import BaseModel
import runtime_config

router = APIRouter()

# Token pricing (you can make these configurable later)
TOKEN_PRICING = {
    "gpt-4": {"input": 0.03, "output": 0.06},  # per 1K tokens
    "gpt-4o": {"input": 0.005, "output": 0.015},
    "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
    "gpt-4o-realtime-preview-2024-12-17": {"input": 0.005, "output": 0.02}  # Realtime pricing
}

def get_active_sessions(limit: int = 100):
    """
    Get active user sessions from the database.
    Active sessions are those with interactions in the last 24 hours.
    """
    try:
        def _impl():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            uuid, 
                            MAX(created_at) as last_interaction,
                            COUNT(*) as message_count
                        FROM session_memory
                        GROUP BY uuid
                        ORDER BY last_interaction DESC
                        LIMIT %s
                    """, (limit,))
                    
                    sessions = []
                    for row in cur.fetchall():
                        uuid, last_interaction, message_count = row
                        
                        # Get additional stats
                        cur.execute("""
                            SELECT
                                COUNT(CASE WHEN role = 'user' THEN 1 END) as user_messages,
                                COUNT(CASE WHEN role = 'assistant' THEN 1 END) as assistant_messages
                            FROM session_memory
                            WHERE uuid = %s
                        """, (uuid,))
                        
                        message_stats = cur.fetchone()
                        if message_stats:
                            user_messages, assistant_messages = message_stats
                        else:
                            user_messages, assistant_messages = 0, 0
                        
                        # Get session summary if available
                        summary = get_summary(uuid) or ""
                        
                        sessions.append({
                            "uuid": uuid,
                            "last_interaction": last_interaction.isoformat() if last_interaction else None,
                            "message_count": message_count,
                            "user_messages": user_messages,
                            "assistant_messages": assistant_messages,
                            "summary": summary[:100] + "..." if len(summary) > 100 else summary
                        })
                    
                    return sessions
        
        return execute_db_operation(_impl)
    except Exception as e:
        print(f"Error getting active sessions: {e}")
        return []

class SummaryUpdate(BaseModel):
    summary: str

@router.post("/sessions/{uuid}/summary")
async def update_session_summary(uuid: str, data: SummaryUpdate):
    """
    Update the session summary.
    """
    from memory.persistent_memory import set_summary
    
    try:
        set_summary(uuid, data.summary)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def estimate_tokens(text: str) -> int:
    """Rough token estimation (1 token ≈ 4 characters for English)"""
    return len(text) // 4

def calculate_session_cost(session_data: dict) -> dict:
    """Calculate estimated cost for a session"""
    total_input_tokens = 0
    total_output_tokens = 0
    
    # Get current model from runtime config
    current_model = runtime_config.get("GPT_MODEL", "gpt-4")
    realtime_model = runtime_config.get("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17")
    
    # Estimate tokens from conversation
    for interaction in session_data.get("conversation", []):
        text = interaction.get("message", "")
        tokens = estimate_tokens(text)
        
        if interaction.get("role") == "user":
            total_input_tokens += tokens
        else:  # assistant
            total_output_tokens += tokens
    
    # Use realtime model pricing (since most sessions are realtime)
    pricing = TOKEN_PRICING.get(realtime_model, TOKEN_PRICING["gpt-4o"])
    
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

def get_session_deep_dive(uuid: str):
    """Get comprehensive session analysis with memory system details"""
    try:
        # Get basic session data
        conversation = get_recent_interactions(uuid, limit=100)  # Get more for analysis
        print(f"🔍 DEBUG: Conversation count = {len(conversation)}")
        summary = get_summary(uuid)
        print(f"🔍 DEBUG: Summary = {summary}")
        memory_stats = get_memory_stats(uuid)
        print(f"🔍 DEBUG: Memory stats = {memory_stats}")
        actual_char_count = sum(len(interaction.get("message", "")) for interaction in conversation)
        print(f"🔍 DEBUG: Actual char count from conversation = {actual_char_count}")
        
        # Get session configuration snapshot
        current_config = {
            "system_prompt": runtime_config.get("SYSTEM_PROMPT", ""),
            "tone_style": runtime_config.get("TONE_STYLE", "empathetic"),
            "temperature": runtime_config.get("TEMPERATURE", 0.7),
            "model": runtime_config.get("GPT_MODEL", "gpt-4"),
            "realtime_model": runtime_config.get("REALTIME_MODEL", "gpt-4o-realtime-preview-2024-12-17"),
            "session_memory_limit": runtime_config.get("SESSION_MEMORY_CHAR_LIMIT", 15000)
        }
        
        # Analyze memory transitions
        memory_transitions = analyze_memory_transitions(conversation, memory_stats)
        
        # Build sample prompt construction
        prompt_construction = build_prompt_construction_example(uuid, current_config)
        
        # Calculate costs
        cost_analysis = calculate_session_cost({"conversation": conversation})
             
        # Get session stats with enhanced data
        def _get_enhanced_stats():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_messages,
                            MIN(created_at) as first_message,
                            MAX(created_at) as last_message,
                            COUNT(CASE WHEN role = 'user' THEN 1 END) as user_messages,
                            COUNT(CASE WHEN role = 'assistant' THEN 1 END) as assistant_messages,
                            AVG(LENGTH(message)) as avg_message_length
                        FROM session_memory
                        WHERE uuid = %s
                    """, (uuid,))
                    
                    row = cur.fetchone()
                    if not row:
                        return {}
                    
                    total, first, last, user, assistant, avg_length = row
                    duration = (last - first).total_seconds() / 60 if first and last else 0
                    
                    return {
                        "total_messages": total,
                        "first_message": first.isoformat() if first else None,
                        "last_message": last.isoformat() if last else None,
                        "user_messages": user,
                        "assistant_messages": assistant,
                        "session_duration": round(duration, 1),
                        "avg_message_length": round(avg_length, 1) if avg_length else 0
                    }
        
        stats = execute_db_operation(_get_enhanced_stats)
        
        return {
            "uuid": uuid,
            "conversation": conversation,
            "summary": summary,
            "stats": stats,
            "memory_stats": memory_stats,
            "memory_transitions": memory_transitions,
            "prompt_construction": prompt_construction,
            "cost_analysis": cost_analysis,
            "session_config": current_config
        }
        
    except Exception as e:
        print(f"Error getting session deep dive: {e}")
        return {"uuid": uuid, "error": str(e)}

def analyze_memory_transitions(conversation: list, memory_stats: dict) -> list:
    """Analyze memory transitions by detecting character count resets and persistent memory growth"""
    transitions = []
    
    # Get current state
    current_chars = memory_stats.get('session_memory_chars', 0)
    current_persistent_chars = memory_stats.get('persistent_memory_chars', 0)
    limit = memory_stats.get('session_memory_limit', 15000)
    
    # Calculate total conversation characters
    total_conversation_chars = sum(len(interaction.get("message", "")) for interaction in conversation if isinstance(interaction, dict))
    
    # Detection logic: If we have substantial conversation but low session memory,
    # AND we have persistent memory, it indicates summarization occurred
    if (total_conversation_chars > limit * 1.5 and  # We've had more than 1.5x the limit worth of conversation
        current_chars < limit * 0.8 and             # But current session memory is less than 80% of limit
        current_persistent_chars > 50):             # And we have substantial persistent memory
        
        # Estimate how many cycles based on total conversation vs current session memory
        estimated_cycles = max(1, int((total_conversation_chars - current_chars) / limit))
        
        for cycle in range(estimated_cycles):
            transitions.append({
                "cycle_number": cycle + 1,
                "trigger": "Memory reset detected (estimated)",
                "estimated_chars_before_reset": limit,
                "method": "Character pattern analysis"
            })
    
    return transitions
    
    return transitions

def build_prompt_construction_example(uuid: str, config: dict) -> dict:
    """Build an example of how prompts are constructed"""
    
    # Get components that would be used in final prompt
    system_prompt = config.get("system_prompt", "")
    if system_prompt and "{tone_style}" in system_prompt:
        system_prompt = system_prompt.format(tone_style=config.get("tone_style", "empathetic"))
    
    persistent_summary = get_summary(uuid)
    recent_session = get_recent_interactions(uuid, limit=5)
    
    # Build context parts like in realtime_chat.py
    context_parts = []
    
    if persistent_summary:
        context_parts.append(f"User Background:\n{persistent_summary}")
    
    if recent_session:
        conversation_context = []
        for interaction in recent_session[-5:]:  # Last 5 interactions
            if isinstance(interaction, dict):
                role = interaction.get("role", "").title()
                message = interaction.get("message", "")
                conversation_context.append(f"{role}: {message}")
        
        if conversation_context:
            context_parts.append("Recent Conversation:\n" + "\n".join(conversation_context))
    
    # Sample RAG context (simulate what would be injected)
    sample_rag = "Relevant Information:\nMobeus is an AI assistant platform that provides comprehensive knowledge base search capabilities..."
    context_parts.append(sample_rag)
    
    full_context = "\n\n".join(context_parts)
    
    # Build COMPLETE final prompt as it would actually be sent
    final_prompt_parts = []
    final_prompt_parts.append(f"SYSTEM INSTRUCTIONS:\n{system_prompt}")
    
    if full_context.strip():
        final_prompt_parts.append(f"CONTEXT:\n{full_context}")
    
    final_prompt_parts.append("USER: [Latest user message would be inserted here]")
    
    final_prompt = "\n\n" + "="*50 + "\n\n".join(final_prompt_parts) + "\n\n" + "="*50
    
    return {
        "system_prompt": system_prompt,
        "system_prompt_length": len(system_prompt),
        "persistent_summary": persistent_summary,
        "persistent_summary_length": len(persistent_summary) if persistent_summary else 0,
        "recent_session_length": sum(len(i.get("message", "")) for i in recent_session if isinstance(i, dict)),
        "context_parts": context_parts,
        "full_context": full_context,
        "full_context_length": len(full_context),
        "final_prompt": final_prompt,
        "final_prompt_length": len(final_prompt),
        "estimated_tokens": estimate_tokens(final_prompt)
    }

@router.get("/sessions/{uuid}/deep-dive", response_class=HTMLResponse)
async def session_deep_dive(
    request: Request,
    uuid: str = Path(..., description="Session UUID")
):
    """Enhanced session view with complete memory system visibility"""
    # DEBUG: This should ALWAYS print if function is called
    print(f"🚨 FUNCTION CALLED: session_deep_dive with UUID: {uuid}")
    print(f"🚨 REQUEST PATH: {request.url}")
    
    session = get_session_deep_dive(uuid)
    session_json = json.dumps(session, default=str)  # Handle datetime serialization
    
    # Safely extract all values to avoid .get() errors in HTML
    stats = session.get('stats', {})
    cost_analysis = session.get('cost_analysis', {})
    memory_stats = session.get('memory_stats', {})
    session_config = session.get('session_config', {})
    prompt_construction = session.get('prompt_construction', {})
    conversation = session.get('conversation', [])
    memory_transitions = session.get('memory_transitions', [])
    summary = session.get('summary', '')
    
    # Ensure stats is a dict before accessing .get()
    if not isinstance(stats, dict):
        stats = {}
    if not isinstance(cost_analysis, dict):
        cost_analysis = {}
    if not isinstance(memory_stats, dict):
        memory_stats = {}
    if not isinstance(session_config, dict):
        session_config = {}
    if not isinstance(prompt_construction, dict):
        prompt_construction = {}

    # Extract individual values
    total_messages = stats.get('total_messages', 0)
    total_tokens = cost_analysis.get('total_tokens', 0)
    total_cost = cost_analysis.get('total_cost', 0)
    session_duration = stats.get('session_duration', 0)
    current_chars = memory_stats.get('session_memory_chars', 0)
    memory_cycles = len(memory_transitions)
    
    # Cost analysis values
    input_tokens = cost_analysis.get('input_tokens', 0)
    output_tokens = cost_analysis.get('output_tokens', 0)
    input_cost = cost_analysis.get('input_cost', 0)
    output_cost = cost_analysis.get('output_cost', 0)
    model_used = cost_analysis.get('model_used', 'Unknown')
    
    # Memory system values
    total_interactions = len(conversation) 
    session_memory_limit = memory_stats.get('session_memory_limit', 15000)
    summary_length = len(summary) if summary else 0
    summary_status = 'Active' if summary else 'Empty'
    
    # Prompt construction values
    system_prompt = prompt_construction.get('system_prompt', '')
    system_prompt_length = prompt_construction.get('system_prompt_length', 0)
    persistent_summary = prompt_construction.get('persistent_summary', '') or 'No persistent memory'
    persistent_summary_length = prompt_construction.get('persistent_summary_length', 0)
    recent_session_length = prompt_construction.get('recent_session_length', 0)
    context_parts = prompt_construction.get('context_parts', [])
    final_prompt = prompt_construction.get('final_prompt', '')
    estimated_tokens = prompt_construction.get('estimated_tokens', 0)
    
    # Generate conversation HTML
    conversation_html = ""
    for interaction in conversation[-10:]:  # Last 10 messages
        if isinstance(interaction, dict):
            role = interaction.get("role", "")
            message = interaction.get("message", "")
            created_at = interaction.get("created_at", "")
        else:
            role = ""
            message = str(interaction)
            created_at = ""
        message_preview = message[:200] + ('...' if len(message) > 200 else '')
        
        conversation_html += f'''
        <div class="message {role}">
            <div class="message-header">
                <span>{role.title()}</span>
                <span>{created_at}</span>
            </div>
            <div class="message-content">{message_preview}</div>
        </div>
        '''
    
    # Generate context parts HTML
    context_html = ""
    for i, part in enumerate(context_parts[:2]):
        context_html += f"<div>{part}</div>"
        if i < len(context_parts[:2]) - 1:
            context_html += "<br><br>"

    print(f"🚨 FINAL SESSION DATA KEYS: {list(session.keys())}")
    print(f"🚨 SESSION STATS: {session.get('stats', 'NO STATS')}")
    
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
            
            .matrix-bg {{
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: 
                    radial-gradient(circle at 20% 80%, rgba(0, 255, 65, 0.1) 0%, transparent 50%),
                    radial-gradient(circle at 80% 20%, rgba(37, 99, 235, 0.1) 0%, transparent 50%);
                pointer-events: none;
                z-index: 0;
            }}
            
            .container {{
                position: relative;
                z-index: 1;
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
            
            .code-block {{
                background: var(--code-bg);
                border: 1px solid var(--border-color);
                border-radius: 0.5rem;
                padding: 1rem;
                font-family: 'Courier New', monospace;
                font-size: 0.875rem;
                white-space: pre-wrap;
                overflow-x: auto;
                max-height: 300px;
                overflow-y: auto;
                color: var(--matrix-green);
            }}
            
            .memory-flow {{
                display: flex;
                flex-direction: column;
                gap: 1rem;
            }}
            
            .memory-stage {{
                padding: 1rem;
                background: var(--code-bg);
                border-radius: 0.5rem;
                border-left: 4px solid var(--accent-color);
            }}
            
            .memory-stage-title {{
                font-weight: bold;
                color: var(--accent-color);
                margin-bottom: 0.5rem;
            }}
            
            .conversation-flow {{
                display: flex;
                flex-direction: column;
                gap: 1rem;
                max-height: 400px;
                overflow-y: auto;
            }}
            
            .message {{
                padding: 1rem;
                border-radius: 0.5rem;
                border-left: 4px solid;
            }}
            
            .message.user {{
                background: rgba(37, 99, 235, 0.1);
                border-left-color: var(--primary-color);
            }}
            
            .message.assistant {{
                background: rgba(6, 214, 160, 0.1);
                border-left-color: var(--accent-color);
            }}
            
            .message-header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 0.5rem;
                font-size: 0.875rem;
                opacity: 0.8;
            }}
            
            .message-content {{
                font-size: 0.9rem;
                line-height: 1.4;
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
            
            .prompt-section {{
                margin-bottom: 1.5rem;
            }}
            
            .prompt-part {{
                margin-bottom: 1rem;
                padding: 1rem;
                background: var(--code-bg);
                border-radius: 0.5rem;
                border-left: 4px solid var(--matrix-green);
            }}
            
            .prompt-part-title {{
                font-weight: bold;
                color: var(--matrix-green);
                margin-bottom: 0.5rem;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .token-count {{
                font-size: 0.75rem;
                color: var(--accent-color);
                background: rgba(6, 214, 160, 0.1);
                padding: 0.25rem 0.5rem;
                border-radius: 0.25rem;
            }}
            
            .tabs {{
                display: flex;
                border-bottom: 1px solid var(--border-color);
                margin-bottom: 1rem;
            }}
            
            .tab {{
                padding: 0.75rem 1.5rem;
                background: none;
                border: none;
                color: var(--text-color);
                cursor: pointer;
                font-family: inherit;
                transition: all 0.3s ease;
            }}
            
            .tab.active {{
                color: var(--matrix-green);
                border-bottom: 2px solid var(--matrix-green);
            }}
            
            .tab-content {{
                display: none;
            }}
            
            .tab-content.active {{
                display: block;
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
        <div class="matrix-bg"></div>
        
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
                    <span class="card-title">Session Matrix</span>
                </div>
                <div class="metrics-grid">
                    <div class="metric">
                        <div class="metric-value">{total_messages}</div>
                        <div class="metric-label">Total Messages</div>
                    </div>
                    <div class="metric">
                        <div class="metric-value">{total_tokens}</div>
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
                        <span class="card-title">Cost Analysis</span>
                    </div>
                    <div class="cost-breakdown">
                        <div class="cost-item">
                            <div class="cost-value">{input_tokens}</div>
                            <div class="cost-label">Input Tokens</div>
                        </div>
                        <div class="cost-item">
                            <div class="cost-value">{output_tokens}</div>
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
                    <div class="memory-flow">
                        <div class="memory-stage">
                            <div class="memory-stage-title">Session Memory</div>
                            <div>Characters: {current_chars} / {session_memory_limit}</div>
                            <div>Messages: {total_interactions}</div>
                        </div>
                        <div class="memory-stage">
                            <div class="memory-stage-title">Persistent Memory</div>
                            <div>Summary Length: {summary_length}</div>
                            <div>Status: {summary_status}</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Prompt Construction -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">🔧</span>
                    <span class="card-title">Prompt Construction Analysis</span>
                </div>
                
                <div class="tabs">
                    <button class="tab active" onclick="showTab('system-prompt')">System Prompt</button>
                    <button class="tab" onclick="showTab('context-assembly')">Context Assembly</button>
                    <button class="tab" onclick="showTab('final-prompt')">Final Prompt</button>
                </div>
                
                <div id="system-prompt" class="tab-content active">
                    <div class="prompt-part">
                        <div class="prompt-part-title">
                            System Instructions
                            <span class="token-count">{system_prompt_length} chars</span>
                        </div>
                        <div class="code-block">{system_prompt[:2000]}{'...' if len(system_prompt) > 2000 else ''}</div>
                    </div>
                </div>
                
                <div id="context-assembly" class="tab-content">
                    <div class="prompt-part">
                        <div class="prompt-part-title">
                            Persistent Memory
                            <span class="token-count">{persistent_summary_length} chars</span>
                        </div>
                        <div class="code-block">{persistent_summary}</div>
                    </div>
                    <div class="prompt-part">
                        <div class="prompt-part-title">
                            Recent Session Context
                            <span class="token-count">{recent_session_length} chars</span>
                        </div>
                        <div class="code-block">{context_html}</div>
                    </div>
                </div>
                
                <div id="final-prompt" class="tab-content">
                    <div class="prompt-part">
                        <div class="prompt-part-title">
                            Complete Assembled Prompt
                            <span class="token-count">~{estimated_tokens} tokens</span>
                        </div>
                        <div class="code-block">{final_prompt[:3000]}{'...' if len(final_prompt) > 3000 else ''}</div>
                    </div>
                </div>
            </div>
            
            <!-- Conversation Flow -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">💬</span>
                    <span class="card-title">Conversation Flow</span>
                </div>
                <div class="conversation-flow">
                    {conversation_html}
                </div>
            </div>
            
            <!-- Session Configuration -->
            <div class="card">
                <div class="card-header">
                    <span class="card-icon">⚙️</span>
                    <span class="card-title">Active Configuration</span>
                </div>
                <div class="code-block">{json.dumps(session_config, indent=2)}</div>
            </div>
        </div>
        
        <script>
            const sessionData = {session_json};
            
            function showTab(tabName) {{
                // Hide all tab contents
                document.querySelectorAll('.tab-content').forEach(content => {{
                    content.classList.remove('active');
                }});
                
                // Remove active class from all tabs
                document.querySelectorAll('.tab').forEach(tab => {{
                    tab.classList.remove('active');
                }});
                
                // Show selected tab content
                document.getElementById(tabName).classList.add('active');
                
                // Add active class to clicked tab
                event.target.classList.add('active');
            }}
            
            // Add some Matrix-style effects
            function createMatrixEffect() {{
                const chars = '01アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲン';
                const canvas = document.createElement('canvas');
                canvas.style.position = 'fixed';
                canvas.style.top = '0';
                canvas.style.left = '0';
                canvas.style.width = '100%';
                canvas.style.height = '100%';
                canvas.style.pointerEvents = 'none';
                canvas.style.zIndex = '0';
                canvas.style.opacity = '0.1';
                document.body.appendChild(canvas);
                
                const ctx = canvas.getContext('2d');
                canvas.width = window.innerWidth;
                canvas.height = window.innerHeight;
                
                const drops = [];
                for (let i = 0; i < canvas.width / 20; i++) {{
                    drops[i] = 1;
                }}
                
                function draw() {{
                    ctx.fillStyle = 'rgba(15, 23, 42, 0.05)';
                    ctx.fillRect(0, 0, canvas.width, canvas.height);
                    
                    ctx.fillStyle = '#00ff41';
                    ctx.font = '12px monospace';
                    
                    for (let i = 0; i < drops.length; i++) {{
                        const text = chars[Math.floor(Math.random() * chars.length)];
                        ctx.fillText(text, i * 20, drops[i] * 20);
                        
                        if (drops[i] * 20 > canvas.height && Math.random() > 0.975) {{
                            drops[i] = 0;
                        }}
                        drops[i]++;
                    }}
                }}
                
                setInterval(draw, 100);
            }}
            
            // Start matrix effect after page load
            setTimeout(createMatrixEffect, 1000);
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
    """Enhanced sessions dashboard with deep dive links"""
    
    sessions: List[Dict[str, Any]] = get_active_sessions(limit=limit)
    
    # Add cost estimates to each session - with proper type handling
    for session in sessions:
        if isinstance(session, dict):
            uuid = session.get("uuid", "")
            if uuid:
                # Get real conversation for this session
                real_conversation = get_recent_interactions(uuid, limit=100)
                real_conversation_data = {"conversation": real_conversation}
                session["cost_estimate"] = calculate_session_cost(real_conversation_data).get("total_cost", 0.0)
            else:
                session["cost_estimate"] = 0.0
    
    # Calculate aggregate stats with type safety
    total_sessions = len(sessions)
    total_messages = sum(session.get("message_count", 0) if isinstance(session, dict) else 0 for session in sessions)
    avg_messages = total_messages / total_sessions if total_sessions > 0 else 0
    
    now = datetime.datetime.now()
    active_today = sum(
        1 for session in sessions 
        if isinstance(session, dict) and 
        session.get("last_interaction") and 
        (now - datetime.datetime.fromisoformat(session["last_interaction"])).total_seconds() < 86400
    )
    
    # Generate table rows with type safety
    table_rows = []
    for session in sessions:
        if not isinstance(session, dict):
            continue
            
        uuid = session.get("uuid", "")
        last_interaction = session.get("last_interaction", "")
        message_count = session.get("message_count", 0)
        summary = session.get("summary", "")
        cost_estimate = session.get("cost_estimate", 0.0)
        
        # Check if session is active
        is_active = (
            last_interaction and 
            (now - datetime.datetime.fromisoformat(last_interaction)).total_seconds() < 86400
        )
        
        badge_class = 'badge-active' if is_active else 'badge-inactive'
        badge_text = 'Active' if is_active else 'Inactive'
        date_display = last_interaction.split("T")[0] if last_interaction else ""
        
        table_rows.append(f"""
        <tr>
            <td>
                <div class="truncate">{uuid}</div>
            </td>
            <td>
                {date_display}
                <span class="badge {badge_class}">{badge_text}</span>
            </td>
            <td>{message_count}</td>
            <td>${cost_estimate:.4f}</td>
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
        <title>Mobeus Assistant — Session Management Dashboard</title>
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
            
            h2 {{
                font-size: 1.25rem;
                margin-bottom: 1rem;
            }}
            
            h3 {{
                font-size: 1rem;
                margin-bottom: 0.5rem;
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
            
            .cost-highlight {{
                font-weight: 600;
                color: var(--warning-color);
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
                <span>Sessions</span>
            </div>
            
            <div class="header">
                <h1>🎯 Session Management Dashboard</h1>
            </div>
            
            <div class="card">
                <div class="card-header">
                    📊 Session Overview
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
                            <div class="metric-value">{total_messages}</div>
                            <div class="metric-label">Total Messages</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{avg_messages:.1f}</div>
                            <div class="metric-label">Avg Messages/Session</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="grid-layout">
                <div class="card">
                    <div class="card-header">
                        📈 Session Activity Trend
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="sessionActivityChart"></canvas>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        💬 Message Distribution
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="messageDistributionChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    🔍 Active Sessions
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
            // Parse data
            const dashboardData = {data_json};
            
            // Helper function to format date
            function formatDate(dateString) {{
                if (!dateString) return '';
                const date = new Date(dateString);
                return date.toLocaleDateString();
            }}
            
            // Calculate session activity data
            const activityData = {{}};
            dashboardData.sessions.forEach(session => {{
                if (session.last_interaction) {{
                    const date = formatDate(session.last_interaction);
                    activityData[date] = (activityData[date] || 0) + 1;
                }}
            }});
            
            const activityDates = Object.keys(activityData).sort();
            const activityCounts = activityDates.map(date => activityData[date]);
            
            // Session Activity Chart
            const sessionActivityCtx = document.getElementById('sessionActivityChart').getContext('2d');
            new Chart(sessionActivityCtx, {{
                type: 'line',
                data: {{
                    labels: activityDates,
                    datasets: [{{
                        label: 'Active Sessions',
                        data: activityCounts,
                        backgroundColor: 'rgba(37, 99, 235, 0.1)',
                        borderColor: '#2563eb',
                        borderWidth: 2,
                        tension: 0.4,
                        fill: true
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            title: {{
                                display: true,
                                text: 'Number of Sessions'
                            }}
                        }}
                    }}
                }}
            }});
            
            // Message Distribution Chart
            const messageDistributionCtx = document.getElementById('messageDistributionChart').getContext('2d');
            
            // Calculate total messages by role
            let totalUserMessages = 0;
            let totalAssistantMessages = 0;
            
            dashboardData.sessions.forEach(session => {{
                totalUserMessages += session.user_messages || 0;
                totalAssistantMessages += session.assistant_messages || 0;
            }});
            
            new Chart(messageDistributionCtx, {{
                type: 'pie',
                data: {{
                    labels: ['User Messages', 'Assistant Messages'],
                    datasets: [{{
                        data: [totalUserMessages, totalAssistantMessages],
                        backgroundColor: ['#f59e0b', '#3b82f6'],
                        borderColor: ['#d97706', '#2563eb'],
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'right'
                        }}
                    }}
                }}
            }});
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
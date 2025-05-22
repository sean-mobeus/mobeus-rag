# session_dashboard.py
import os
import json
import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Query, Path
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from memory.session_memory import get_recent_interactions
from memory.persistent_memory import get_summary
from memory.db import get_connection, execute_db_operation
from pydantic import BaseModel

router = APIRouter()

# Session tracking logic
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

def get_session_details(uuid: str):
    """
    Get detailed information for a specific session.
    """
    try:
        # Get conversation history
        conversation = get_recent_interactions(uuid, limit=50)
        
        # Get session summary
        summary = get_summary(uuid)
        
        # Get session stats
        def _get_stats():
            with get_connection() as conn:
                with conn.cursor() as cur:
                    # Get message counts and timestamps
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_messages,
                            MIN(created_at) as first_message,
                            MAX(created_at) as last_message,
                            COUNT(CASE WHEN role = 'user' THEN 1 END) as user_messages,
                            COUNT(CASE WHEN role = 'assistant' THEN 1 END) as assistant_messages
                        FROM session_memory
                        WHERE uuid = %s
                    """, (uuid,))
                    
                    row = cur.fetchone()
                    if not row:
                        return {
                            "total_messages": 0,
                            "first_message": None,
                            "last_message": None,
                            "user_messages": 0,
                            "assistant_messages": 0,
                            "session_duration": 0
                        }
                    
                    total, first, last, user, assistant = row
                    
                    # Calculate session duration in minutes
                    duration = (last - first).total_seconds() / 60 if first and last else 0
                    
                    return {
                        "total_messages": total,
                        "first_message": first.isoformat() if first else None,
                        "last_message": last.isoformat() if last else None,
                        "user_messages": user,
                        "assistant_messages": assistant,
                        "session_duration": round(duration, 1)
                    }
        
        stats = execute_db_operation(_get_stats)
        
        return {
            "uuid": uuid,
            "conversation": conversation,
            "summary": summary,
            "stats": stats
        }
    except Exception as e:
        print(f"Error getting session details: {e}")
        return {
            "uuid": uuid,
            "conversation": [],
            "summary": None,
            "stats": {
                "total_messages": 0,
                "session_duration": 0
            }
        }

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

@router.get("/sessions", response_class=HTMLResponse)
async def sessions_dashboard(
    request: Request,
    limit: int = Query(50, description="Number of sessions to show")
):
    """
    Session management dashboard showing active user sessions.
    """
    sessions = get_active_sessions(limit=limit)
    
    # Calculate aggregate stats
    total_sessions = len(sessions)
    total_messages = sum(session.get("message_count", 0) for session in sessions)
    avg_messages = total_messages / total_sessions if total_sessions > 0 else 0
    
    now = datetime.datetime.now()
    active_today = sum(
        1 for session in sessions 
        if session.get("last_interaction") and 
        (now - datetime.datetime.fromisoformat(session["last_interaction"])).total_seconds() < 86400
    )
    
    # Convert data to JSON for JavaScript
    data_json = json.dumps({
        "sessions": sessions,
        "stats": {
            "total_sessions": total_sessions,
            "total_messages": total_messages,
            "avg_messages": avg_messages,
            "active_today": active_today
        }
    })
    
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
            }}
            
            .card-header {{
                padding: 1rem;
                border-bottom: 1px solid var(--border-color);
                font-weight: 600;
                display: flex;
                justify-content: space-between;
                align-items: center;
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
            }}
            
            .metric-value {{
                font-size: 1.5rem;
                font-weight: 600;
                margin-bottom: 0.25rem;
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
                max-width: 300px;
            }}
            
            @media (max-width: 768px) {{
                .grid-layout {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="dashboard">
            <div class="header">
                <h1>Mobeus Assistant — Session Management Dashboard</h1>
            </div>
            
            <div class="card">
                <div class="card-header">
                    Session Summary
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
                        Session Activity
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="sessionActivityChart"></canvas>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        Message Distribution
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
                    Active Sessions
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
                                    <th>Summary</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {"".join([f"""
                                <tr>
                                    <td>
                                        <div class="truncate">{session.get("uuid", "")}</div>
                                    </td>
                                    <td>
                                        {session.get("last_interaction", "").split("T")[0] if session.get("last_interaction") else ""}
                                        <span class="badge {
                                            'badge-active' if session.get("last_interaction") and 
                                            (now - datetime.datetime.fromisoformat(session["last_interaction"])).total_seconds() < 86400
                                            else 'badge-inactive'
                                        }">
                                            {
                                                'Active' if session.get("last_interaction") and 
                                                (now - datetime.datetime.fromisoformat(session["last_interaction"])).total_seconds() < 86400
                                                else 'Inactive'
                                            }
                                        </span>
                                    </td>
                                    <td>{session.get("message_count", 0)}</td>
                                    <td>
                                        <div class="truncate">{session.get("summary", "")}</div>
                                    </td>
                                    <td>
                                        <a href="/sessions/{session.get("uuid", "")}">View Details</a>
                                    </td>
                                </tr>
                                """ for session in sessions])}
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

@router.get("/sessions/{uuid}", response_class=HTMLResponse)
async def session_details(
    request: Request,
    uuid: str = Path(..., description="Session UUID")
):
    """
    Detailed view of a specific session including conversation history.
    """
    session = get_session_details(uuid)
    
    # Convert data to JSON for JavaScript
    session_json = json.dumps(session)
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mobeus Assistant — Session Details</title>
        <style>
            :root {{
                --primary-color: #2563eb;
                --primary-light: rgba(37, 99, 235, 0.1);
                --secondary-color: #1e40af;
                --background-color: #f9fafb;
                --card-color: #ffffff;
                --text-color: #1f2937;
                --border-color: #e5e7eb;
                --user-bubble: #3b82f6;
                --assistant-bubble: #f3f4f6;
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
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 1.5rem;
            }}
            
            .header {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1.5rem;
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
            
            .breadcrumb a:hover {{
                text-decoration: underline;
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
            }}
            
            .card-header {{
                padding: 1rem;
                border-bottom: 1px solid var(--border-color);
                font-weight: 600;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .card-body {{
                padding: 1rem;
            }}
            
            .metrics-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
                gap: 1rem;
                margin-bottom: 1.5rem;
            }}
            
            .metric {{
                background-color: #f9fafb;
                border-radius: 0.5rem;
                padding: 1rem;
                text-align: center;
            }}
            
            .metric-value {{
                font-size: 1.25rem;
                font-weight: 600;
                margin-bottom: 0.25rem;
            }}
            
            .metric-label {{
                font-size: 0.75rem;
                color: #6b7280;
                text-transform: uppercase;
                letter-spacing: 0.05em;
            }}
            
            .summary-section {{
                margin-bottom: 1.5rem;
            }}
            
            .form-group {{
                margin-bottom: 1rem;
            }}
            
            label {{
                display: block;
                margin-bottom: 0.5rem;
                font-weight: 500;
            }}
            
            textarea {{
                width: 100%;
                padding: 0.75rem;
                border: 1px solid var(--border-color);
                border-radius: 0.375rem;
                font-family: inherit;
                font-size: 0.875rem;
                min-height: 100px;
            }}
            
            button {{
                padding: 0.5rem 1rem;
                background-color: var(--primary-color);
                color: white;
                border: none;
                border-radius: 0.375rem;
                font-weight: 500;
                cursor: pointer;
            }}
            
            button:hover {{
                background-color: var(--secondary-color);
            }}
            
            .messages-container {{
                display: flex;
                flex-direction: column;
                gap: 1rem;
                margin-top: 1rem;
            }}
            
            .message {{
                display: flex;
                gap: 1rem;
                max-width: 80%;
            }}
            
            .message.user {{
                align-self: flex-end;
            }}
            
            .message.assistant {{
                align-self: flex-start;
            }}
            
            .message-bubble {{
                padding: 0.75rem 1rem;
                border-radius: 0.75rem;
                font-size: 0.875rem;
            }}
            
            .message.user .message-bubble {{
                background-color: var(--user-bubble);
                color: white;
                border-bottom-right-radius: 0;
            }}
            
            .message.assistant .message-bubble {{
                background-color: var(--assistant-bubble);
                border-bottom-left-radius: 0;
            }}
            
            .message-time {{
                font-size: 0.75rem;
                color: #6b7280;
                margin-top: 0.25rem;
            }}
            
            .success-message {{
                padding: 0.75rem;
                background-color: rgba(16, 185, 129, 0.1);
                border: 1px solid #10b981;
                border-radius: 0.375rem;
                color: #065f46;
                margin-bottom: 1rem;
                display: none;
            }}
            
            .error-message {{
                padding: 0.75rem;
                background-color: rgba(239, 68, 68, 0.1);
                border: 1px solid #ef4444;
                border-radius: 0.375rem;
                color: #b91c1c;
                margin-bottom: 1rem;
                display: none;
            }}
            
            @media (max-width: 768px) {{
                .metrics-grid {{
                    grid-template-columns: 1fr 1fr;
                }}
                
                .message {{
                    max-width: 90%;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="breadcrumb">
                <a href="/sessions">Sessions</a>
                <span>/</span>
                <span>Session Details</span>
            </div>
            
            <div class="header">
                <h1>Session Details</h1>
            </div>
            
            <div class="card">
                <div class="card-header">
                    Session Overview
                </div>
                <div class="card-body">
                    <div class="metrics-grid">
                        <div class="metric">
                            <div class="metric-value">{session["stats"].get("total_messages", 0)}</div>
                            <div class="metric-label">Total Messages</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{session["stats"].get("user_messages", 0)}</div>
                            <div class="metric-label">User Messages</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{session["stats"].get("assistant_messages", 0)}</div>
                            <div class="metric-label">Assistant Messages</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{session["stats"].get("session_duration", 0)}</div>
                            <div class="metric-label">Duration (min)</div>
                        </div>
                    </div>
                    
                    <div class="summary-section">
                        <h3>Session Summary</h3>
                        <div id="success-message" class="success-message">
                            Summary updated successfully!
                        </div>
                        <div id="error-message" class="error-message">
                            Failed to update summary.
                        </div>
                        <div class="form-group">
                            <textarea id="summary-input">{session.get("summary", "")}</textarea>
                        </div>
                        <button id="save-summary">Save Summary</button>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    Conversation History
                </div>
                <div class="card-body">
                    <div class="messages-container" id="conversation">
                        <!-- Will be populated by JavaScript -->
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Parse session data
            const sessionData = {session_json};
            
            // Populate conversation
            const conversationContainer = document.getElementById('conversation');
            
            sessionData.conversation.forEach(message => {{
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${{message.role}}`;
                
                const bubbleDiv = document.createElement('div');
                bubbleDiv.className = 'message-bubble';
                bubbleDiv.textContent = message.message;
                
                messageDiv.appendChild(bubbleDiv);
                conversationContainer.appendChild(messageDiv);
            }});
            
            // Handle summary update
            const summaryInput = document.getElementById('summary-input');
            const saveButton = document.getElementById('save-summary');
            const successMessage = document.getElementById('success-message');
            const errorMessage = document.getElementById('error-message');
            
            saveButton.addEventListener('click', async () => {{
                const summary = summaryInput.value;
                
                try {{
                    const response = await fetch(`/sessions/{session["uuid"]}/summary`, {{
                        method: 'POST',
                        headers: {{
                            'Content-Type': 'application/json'
                        }},
                        body: JSON.stringify({{ summary }})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.success) {{
                        successMessage.style.display = 'block';
                        errorMessage.style.display = 'none';
                        
                        // Hide success message after 3 seconds
                        setTimeout(() => {{
                            successMessage.style.display = 'none';
                        }}, 3000);
                    }} else {{
                        errorMessage.textContent = data.error || 'Failed to update summary.';
                        errorMessage.style.display = 'block';
                        successMessage.style.display = 'none';
                    }}
                }} catch (error) {{
                    console.error('Error updating summary:', error);
                    errorMessage.textContent = 'Failed to update summary. Please try again.';
                    errorMessage.style.display = 'block';
                    successMessage.style.display = 'none';
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

@router.get("/sessions/data")
async def get_sessions_data(
    limit: int = Query(50, description="Number of sessions to return")
):
    """
    API endpoint to get session data as JSON for external use.
    """
    sessions = get_active_sessions(limit=limit)
    
    return JSONResponse({
        "sessions": sessions,
        "total": len(sessions)
    })

@router.get("/sessions/{uuid}/data")
async def get_session_data(
    uuid: str = Path(..., description="Session UUID")
):
    """
    API endpoint to get details for a specific session.
    """
    session = get_session_details(uuid)
    
    return JSONResponse(session)
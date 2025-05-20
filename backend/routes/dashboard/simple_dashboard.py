# simple_dashboard.py
"""
A simplified version of the dashboard without external dependencies
"""
import os
import json
import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from config import DEBUG_LOG_PATH

router = APIRouter()

def format_time(seconds: float) -> str:
    """Format time in seconds to a human-readable string with appropriate units."""
    if seconds < 0.001:
        return f"{seconds * 1000000:.1f}μs"
    elif seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    else:
        return f"{seconds:.2f}s"

def get_log_entries(limit: int = 50, filter_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get log entries from the debug log file.
    
    Args:
        limit: Maximum number of entries to return
        filter_query: Optional string to filter entries by query text
        
    Returns:
        List of log entry dictionaries
    """
    entries = []
    
    try:
        if not os.path.exists(DEBUG_LOG_PATH):
            return entries
            
        with open(DEBUG_LOG_PATH, "r") as f:
            lines = f.readlines()
            
        for line in reversed(lines):
            try:
                entry = json.loads(line)
                
                # Apply filter if provided
                if filter_query and filter_query.lower() not in entry.get("query", "").lower():
                    continue
                    
                # Calculate additional metrics
                timings = entry.get("timings", {})
                if timings:
                    # Calculate retrieval percentage of total time
                    if "retrieval" in timings and "total" in timings and timings["total"] > 0:
                        timings["retrieval_percent"] = (timings["retrieval"] / timings["total"]) * 100
                    
                    # Calculate GPT percentage of total time
                    if "gpt" in timings and "total" in timings and timings["total"] > 0:
                        timings["gpt_percent"] = (timings["gpt"] / timings["total"]) * 100
                        
                    # Format timing values for display
                    for key, value in timings.items():
                        if isinstance(value, (int, float)) and not key.endswith("_percent"):
                            timings[f"{key}_formatted"] = format_time(value)
                
                entries.append(entry)
                
                if len(entries) >= limit:
                    break
            except json.JSONDecodeError:
                continue
    except Exception as e:
        print(f"Error reading log file: {e}")
    
    return entries

@router.get("/api/logs", response_class=JSONResponse)
async def get_logs(
    request: Request,
    limit: int = Query(50, description="Number of log entries to return"),
    filter: Optional[str] = Query(None, description="Filter logs by query text")
):
    """
    API endpoint to get log entries as JSON
    """
    entries = get_log_entries(limit=limit, filter_query=filter)
    
    return JSONResponse({
        "entries": entries,
        "total": len(entries),
        "timestamp": datetime.datetime.now().isoformat()
    })

@router.get("/", response_class=HTMLResponse)
async def simple_dashboard():
    """
    Simple dashboard HTML
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mobeus Assistant — Debug Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                margin: 0;
                padding: 20px;
                background-color: #f9fafb;
                color: #1f2937;
            }
            h1, h2 {
                color: #1f2937;
            }
            .card {
                background-color: white;
                border-radius: 8px;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                padding: 20px;
                margin-bottom: 20px;
            }
            #logs {
                max-height: 600px;
                overflow-y: auto;
            }
            .log-item {
                padding: 10px;
                border-bottom: 1px solid #e5e7eb;
            }
            .log-item:last-child {
                border-bottom: none;
            }
            .query {
                font-weight: bold;
                margin-bottom: 5px;
            }
            .answer {
                color: #4b5563;
                white-space: pre-wrap;
            }
            .timestamp {
                color: #9ca3af;
                font-size: 0.8em;
            }
            .timings {
                display: flex;
                gap: 10px;
                margin: 5px 0;
                flex-wrap: wrap;
            }
            .timing {
                background-color: #f3f4f6;
                padding: 3px 8px;
                border-radius: 16px;
                font-size: 0.8em;
            }
            .good {
                color: #10b981;
            }
            .warning {
                color: #f59e0b;
            }
            .bad {
                color: #ef4444;
            }
            .filters {
                margin-bottom: 20px;
                display: flex;
                gap: 10px;
                align-items: end;
            }
            .field {
                display: flex;
                flex-direction: column;
                gap: 5px;
            }
            label {
                font-size: 0.9em;
                font-weight: 500;
            }
            input, button {
                padding: 8px;
                border: 1px solid #d1d5db;
                border-radius: 4px;
            }
            button {
                background-color: #2563eb;
                color: white;
                border: none;
                cursor: pointer;
            }
            #loading {
                display: none;
                text-align: center;
                padding: 20px;
                color: #6b7280;
            }
        </style>
    </head>
    <body>
        <h1>Debug Dashboard</h1>
        
        <div class="card">
            <div class="filters">
                <div class="field">
                    <label for="limit">Max Entries</label>
                    <input type="number" id="limit" value="50" min="1" max="100">
                </div>
                <div class="field">
                    <label for="filter">Filter Query</label>
                    <input type="text" id="filter" placeholder="Search queries...">
                </div>
                <button id="refresh">Refresh</button>
            </div>
            
            <div id="loading">Loading logs...</div>
            <div id="logs"></div>
        </div>
        
        <script>
            // Get elements
            const logsContainer = document.getElementById('logs');
            const limitInput = document.getElementById('limit');
            const filterInput = document.getElementById('filter');
            const refreshButton = document.getElementById('refresh');
            const loadingElement = document.getElementById('loading');
            
            // Load logs function
            async function loadLogs() {
                try {
                    loadingElement.style.display = 'block';
                    logsContainer.innerHTML = '';
                    
                    const limit = limitInput.value;
                    const filter = filterInput.value;
                    
                    const url = `/api/logs?limit=${limit}${filter ? `&filter=${encodeURIComponent(filter)}` : ''}`;
                    const response = await fetch(url);
                    const data = await response.json();
                    
                    if (data.entries.length === 0) {
                        logsContainer.innerHTML = '<p>No logs found</p>';
                        return;
                    }
                    
                    data.entries.forEach(entry => {
                        const logItem = document.createElement('div');
                        logItem.className = 'log-item';
                        
                        const query = document.createElement('div');
                        query.className = 'query';
                        query.textContent = entry.query || 'No query';
                        
                        const timestamp = document.createElement('div');
                        timestamp.className = 'timestamp';
                        timestamp.textContent = entry.timestamp || '';
                        
                        const timings = document.createElement('div');
                        timings.className = 'timings';
                        
                        if (entry.timings) {
                            for (const [key, value] of Object.entries(entry.timings)) {
                                if (typeof value === 'number' && !key.endsWith('_percent') && !key.endsWith('_formatted')) {
                                    const timing = document.createElement('span');
                                    timing.className = 'timing';
                                    
                                    // Add color classes based on timing values
                                    if (key === 'total') {
                                        if (value < 3) timing.classList.add('good');
                                        else if (value < 5) timing.classList.add('warning');
                                        else timing.classList.add('bad');
                                    } else if (key === 'gpt') {
                                        if (value < 2) timing.classList.add('good');
                                        else if (value < 3) timing.classList.add('warning');
                                        else timing.classList.add('bad');
                                    }
                                    
                                    timing.textContent = `${key}: ${entry.timings[key + '_formatted'] || value.toFixed(2) + 's'}`;
                                    timings.appendChild(timing);
                                }
                            }
                        }
                        
                        const answer = document.createElement('div');
                        answer.className = 'answer';
                        answer.textContent = entry.answer || 'No answer';
                        
                        logItem.appendChild(query);
                        logItem.appendChild(timestamp);
                        logItem.appendChild(timings);
                        logItem.appendChild(answer);
                        
                        logsContainer.appendChild(logItem);
                    });
                } catch (error) {
                    console.error('Error loading logs:', error);
                    logsContainer.innerHTML = `<p>Error loading logs: ${error.message}</p>`;
                } finally {
                    loadingElement.style.display = 'none';
                }
            }
            
            // Add event listeners
            refreshButton.addEventListener('click', loadLogs);
            document.addEventListener('DOMContentLoaded', loadLogs);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)
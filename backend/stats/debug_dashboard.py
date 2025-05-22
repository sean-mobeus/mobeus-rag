# debug_dashboard.py
import os
import json
import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from config import DEBUG_LOG_PATH
import psutil

router = APIRouter()

# Try to import psutil but make it optional
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: psutil not installed. System stats will be unavailable.")

def format_time(seconds: float) -> str:
    """Format time in seconds to a human-readable string with appropriate units."""
    if seconds < 0.001:
        return f"{seconds * 1000000:.1f}μs"
    elif seconds < 1:
        return f"{seconds * 1000:.1f}ms"
    else:
        return f"{seconds:.2f}s"

def get_system_stats() -> Dict[str, Any]:
    """Get system statistics like CPU, memory usage, etc."""
    try:
        if not HAS_PSUTIL:
            return {
                "error": "psutil not installed",
                "cpu_percent": 0,
                "memory_percent": 0,
                "active_connections": 0,
                "uptime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "active_connections": len(psutil.net_connections("inet4")),
            "uptime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
    except Exception as e:
        print(f"Error getting system stats: {e}")
        return {
            "cpu_percent": 0,
            "memory_percent": 0,
            "active_connections": 0,
            "uptime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": str(e)
        }

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

@router.get("/debug", response_class=JSONResponse)
async def debug_dashboard(
    request: Request,
    limit: int = Query(50, description="Number of log entries to show"),
    filter: Optional[str] = Query(None, description="Filter logs by query text")
):
    """
    Simple debug dashboard that returns log entries as JSON.
    """
    entries = get_log_entries(limit=limit, filter_query=filter)
    return JSONResponse(entries)

@router.get("/debug/data")
async def get_debug_data(
    limit: int = Query(50, description="Number of log entries to return"),
    filter: Optional[str] = Query(None, description="Filter logs by query text")
):
    """
    API endpoint to get debug data as JSON for external use.
    """
    entries = get_log_entries(limit=limit, filter_query=filter)
    system_stats = get_system_stats()
    
    return JSONResponse({
        "entries": entries,
        "system_stats": system_stats,
        "summary": {
            "total_entries": len(entries),
            "avg_total_time": sum([entry.get("timings", {}).get("total", 0) for entry in entries]) / max(len(entries), 1),
            "avg_gpt_time": sum([entry.get("timings", {}).get("gpt", 0) for entry in entries]) / max(len(entries), 1),
            "avg_retrieval_time": sum([entry.get("timings", {}).get("retrieval", 0) for entry in entries]) / max(len(entries), 1),
        }
    })

@router.get("/debug/sessions")
async def get_debug_sessions():
    """
    View active sessions and their metrics.
    This is a placeholder that would need integration with actual session tracking.
    """
    # This would need to be implemented with actual session tracking
    sessions = []
    
    html_content = """
    <html>
    <head>
        <title>Mobeus Assistant — Active Sessions</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body { font-family: sans-serif; padding: 2rem; }
            h1 { margin-bottom: 1rem; }
            .empty-state { 
                text-align: center;
                padding: 4rem;
                color: #6b7280;
            }
        </style>
    </head>
    <body>
        <h1>Active Sessions</h1>
        <div class="empty-state">
            <p>No active sessions found.</p>
            <p>Session tracking needs to be implemented.</p>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html_content)
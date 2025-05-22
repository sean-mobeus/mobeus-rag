# routes/dashboard/debug_dashboard.py
import os
import json
import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
import os.path
from config import DEBUG_LOG_PATH

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
    """Get system statistics like CPU, memory usage, etc. with proper error handling."""
    stats = {
        "cpu_percent": 0,
        "memory_percent": 0,
        "active_connections": 0,
        "uptime": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    if not HAS_PSUTIL:
        stats["error"] = "psutil not installed"
        return stats
    
    try:
        stats["cpu_percent"] = psutil.cpu_percent(interval=0.1)
        stats["memory_percent"] = psutil.virtual_memory().percent
        
        # This might fail in some Docker environments due to permission issues
        try:
            stats["active_connections"] = len(psutil.net_connections("inet4"))
        except (psutil.AccessDenied, PermissionError):
            stats["active_connections"] = 0
            stats["connections_error"] = "Permission denied"
            
    except Exception as e:
        print(f"Error getting system stats: {e}")
        stats["error"] = str(e)
    
    return stats

def get_log_entries(limit: int = 50, filter_query: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get log entries from the debug log file with proper error handling.
    
    Args:
        limit: Maximum number of entries to return
        filter_query: Optional string to filter entries by query text
        
    Returns:
        List of log entry dictionaries
    """
    entries = []
    
    try:
        # Check if log file exists and is readable
        if not os.path.exists(DEBUG_LOG_PATH):
            print(f"Warning: Debug log file not found at {DEBUG_LOG_PATH}")
            return entries
            
        # Handle potential file read issues
        try:
            with open(DEBUG_LOG_PATH, "r") as f:
                lines = f.readlines()
        except (PermissionError, IOError) as e:
            print(f"Error reading log file: {e}")
            return entries
            
        # Process log entries with error handling for each line
        for line in reversed(lines):
            try:
                entry = json.loads(line)
                
                # Apply filter if provided
                if filter_query and filter_query.lower() not in entry.get("query", "").lower():
                    continue
                    
                # Calculate additional metrics
                timings = entry.get("timings", {})
                if timings:
                    # Format timing values for display with fallbacks for missing data
                    timings_formatted = {}
                    
                    # Calculate retrieval percentage of total time
                    if "retrieval" in timings and "total" in timings and timings["total"] > 0:
                        timings["retrieval_percent"] = (timings["retrieval"] / timings["total"]) * 100
                        timings_formatted["retrieval_percent"] = f"{timings['retrieval_percent']:.1f}%"
                    
                    # Calculate GPT percentage of total time
                    if "gpt" in timings and "total" in timings and timings["total"] > 0:
                        timings["gpt_percent"] = (timings["gpt"] / timings["total"]) * 100
                        timings_formatted["gpt_percent"] = f"{timings['gpt_percent']:.1f}%"
                    
                    # Format timing values for display
                    for key, value in timings.items():
                        if isinstance(value, (int, float)) and not key.endswith("_percent"):
                            timings_formatted[f"{key}_formatted"] = format_time(value)
                    
                    # Add formatted timings to entry
                    entry["timings_formatted"] = timings_formatted
                
                entries.append(entry)
                
                if len(entries) >= limit:
                    break
            except json.JSONDecodeError:
                # Skip invalid JSON lines without failing
                continue
    except Exception as e:
        print(f"Error processing log entries: {e}")
    
    return entries

@router.get("/debug", response_class=HTMLResponse)
async def debug_dashboard(
    request: Request,
    limit: int = Query(50, description="Number of log entries to show"),
    filter: Optional[str] = Query(None, description="Filter logs by query text")
):
    """
    Debug dashboard with log visualization.
    Returns HTML rendering of the debug information.
    """
    try:
        # Get log entries with proper error handling
        entries = get_log_entries(limit=limit, filter_query=filter)
        
        # Get system stats
        system_stats = get_system_stats()
        
        # Calculate summary statistics with fallbacks for empty entries
        summary: Dict[str, float] = {
            "total_entries": float(len(entries)),
            "avg_total_time": 0.0,
            "avg_gpt_time": 0.0,
            "avg_retrieval_time": 0.0,
        }
        
        if entries:
            # Calculate averages with proper error handling
            total_times = [e.get("timings", {}).get("total", 0) for e in entries]
            gpt_times = [e.get("timings", {}).get("gpt", 0) for e in entries]
            retrieval_times = [e.get("timings", {}).get("retrieval", 0) for e in entries]
            
            summary["avg_total_time"] = sum(total_times) / max(len(total_times), 1)
            summary["avg_gpt_time"] = sum(gpt_times) / max(len(gpt_times), 1)
            summary["avg_retrieval_time"] = sum(retrieval_times) / max(len(retrieval_times), 1)
        
        # Render HTML with all components
        # Using a more modular approach
        html = render_debug_dashboard(entries, system_stats, summary, limit, filter)
        return HTMLResponse(content=html)
        
    except Exception as e:
        # Fallback HTML in case of error
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Debug Dashboard - Error</title>
            <style>
                body {{ font-family: system-ui, sans-serif; padding: 2rem; max-width: 800px; margin: 0 auto; }}
                .error {{ background-color: #fee2e2; border: 1px solid #ef4444; padding: 1rem; border-radius: 0.375rem; }}
                pre {{ background-color: #f3f4f6; padding: 1rem; overflow: auto; border-radius: 0.375rem; }}
            </style>
        </head>
        <body>
            <h1>Debug Dashboard</h1>
            <div class="error">
                <h2>Error rendering dashboard</h2>
                <p>An error occurred while rendering the dashboard.</p>
                <pre>{str(e)}</pre>
            </div>
            <p><a href="./">Return to Main Dashboard</a></p>
            <hr>
            <h3>Raw JSON API</h3>
            <p>You can still access the debug data as JSON via: <a href="./debug/data?limit={limit}&filter={filter or ''}">./debug/data</a></p>
        </body>
        </html>
        """
        return HTMLResponse(content=error_html)

def render_debug_dashboard(entries, system_stats, summary, limit, filter):
    """
    Render the debug dashboard HTML with proper error handling.
    Breaks down the template into manageable chunks.
    """
    # CSS styles
    css = """
    <style>
        :root {
            --primary: #2563eb;
            --primary-light: #dbeafe;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --gray-50: #f9fafb;
            --gray-100: #f3f4f6;
            --gray-200: #e5e7eb;
            --gray-300: #d1d5db;
            --gray-500: #6b7280;
            --gray-700: #374151;
            --gray-900: #111827;
        }
        
        body {
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.5;
            color: var(--gray-900);
            background-color: var(--gray-50);
            margin: 0;
            padding: 20px;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--gray-200);
        }
        
        h1, h2, h3, h4 {
            margin-top: 0;
            margin-bottom: 0.5rem;
        }
        
        h1 {
            font-size: 1.5rem;
            font-weight: 600;
            color: var(--gray-900);
        }
        
        .card {
            background-color: white;
            border-radius: 0.5rem;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            margin-bottom: 1.5rem;
            overflow: hidden;
        }
        
        .card-header {
            padding: 1rem;
            background-color: var(--gray-50);
            border-bottom: 1px solid var(--gray-200);
            font-weight: 500;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .card-body {
            padding: 1rem;
        }
        
        .filters {
            display: flex;
            gap: 1rem;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
        }
        
        .form-group {
            display: flex;
            flex-direction: column;
            min-width: 200px;
        }
        
        label {
            font-size: 0.875rem;
            font-weight: 500;
            margin-bottom: 0.5rem;
            color: var(--gray-700);
        }
        
        input, select {
            padding: 0.5rem;
            border: 1px solid var(--gray-300);
            border-radius: 0.375rem;
            font-size: 0.875rem;
            line-height: 1.25rem;
        }
        
        button {
            background-color: var(--primary);
            color: white;
            font-weight: 500;
            padding: 0.5rem 1rem;
            border: none;
            border-radius: 0.375rem;
            cursor: pointer;
        }
        
        button:hover {
            opacity: 0.9;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 1.5rem;
        }
        
        .stat-card {
            background-color: white;
            border-radius: 0.5rem;
            padding: 1rem;
            box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
            text-align: center;
        }
        
        .stat-value {
            font-size: 1.5rem;
            font-weight: 600;
            margin-bottom: 0.25rem;
        }
        
        .stat-label {
            font-size: 0.875rem;
            color: var(--gray-500);
        }
        
        .good {
            color: var(--success);
        }
        
        .warning {
            color: var(--warning);
        }
        
        .bad {
            color: var(--danger);
        }
        
        table {
            width: 100%;
            border-collapse: collapse;
        }
        
        th, td {
            text-align: left;
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--gray-200);
        }
        
        th {
            font-weight: 500;
            color: var(--gray-700);
            background-color: var(--gray-50);
        }
        
        tr:hover {
            background-color: var(--gray-50);
        }
        
        pre {
            background-color: var(--gray-100);
            padding: 0.75rem;
            border-radius: 0.375rem;
            overflow: auto;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.875rem;
            white-space: pre-wrap;
            word-break: break-word;
        }
        
        .badge {
            display: inline-block;
            padding: 0.25rem 0.5rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 500;
        }
        
        .badge-success {
            background-color: #d1fae5;
            color: #065f46;
        }
        
        .badge-warning {
            background-color: #fef3c7;
            color: #92400e;
        }
        
        .badge-danger {
            background-color: #fee2e2;
            color: #b91c1c;
        }
        
        .pagination {
            display: flex;
            justify-content: center;
            margin-top: 1rem;
        }
        
        .pagination button {
            margin: 0 0.25rem;
        }
        
        .footer {
            text-align: center;
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid var(--gray-200);
            font-size: 0.875rem;
            color: var(--gray-500);
        }
        
        .breadcrumb {
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.875rem;
            margin-bottom: 1rem;
        }
        
        .breadcrumb a {
            color: var(--primary);
            text-decoration: none;
        }
        
        .breadcrumb span {
            color: var(--gray-500);
        }
        
        .no-data {
            text-align: center;
            padding: 3rem 1rem;
            color: var(--gray-500);
        }
        
        details {
            margin-bottom: 0.5rem;
        }
        
        summary {
            cursor: pointer;
            padding: 0.5rem;
            background-color: var(--gray-50);
            border-radius: 0.375rem;
            font-weight: 500;
        }
        
        summary:hover {
            background-color: var(--gray-100);
        }
        
        @media (max-width: 768px) {
            .stats-grid {
                grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
            }
            
            .header {
                flex-direction: column;
                align-items: flex-start;
            }
            
            .filters {
                flex-direction: column;
            }
        }
    </style>
    """
    
    # Create header and filter form
    filter_value = filter or ""
    header_html = f"""
    <div class="container">
        <div class="breadcrumb">
            <a href="./">Dashboard</a>
            <span>/</span>
            <span>Debug Logs</span>
        </div>
        
        <div class="header">
            <h1>Mobeus Assistant — Debug Logs</h1>
        </div>
        
        <div class="card">
            <div class="card-header">
                Filters
            </div>
            <div class="card-body">
                <form method="GET" action="./debug">
                    <div class="filters">
                        <div class="form-group">
                            <label for="limit">Max Entries</label>
                            <input type="number" id="limit" name="limit" value="{limit}" min="1" max="1000">
                        </div>
                        
                        <div class="form-group">
                            <label for="filter">Filter by Query</label>
                            <input type="text" id="filter" name="filter" value="{filter_value}" placeholder="Filter by query text...">
                        </div>
                        
                        <div class="form-group" style="justify-content: flex-end;">
                            <button type="submit">Apply Filters</button>
                        </div>
                    </div>
                </form>
            </div>
        </div>
    """
    
    # Create system stats section
    system_stats_html = f"""
    <div class="card">
        <div class="card-header">
            System Stats
        </div>
        <div class="card-body">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value {'warning' if system_stats.get('cpu_percent', 0) > 70 else 'good'}">
                        {system_stats.get('cpu_percent', 0)}%
                    </div>
                    <div class="stat-label">CPU Usage</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-value {'warning' if system_stats.get('memory_percent', 0) > 80 else 'good'}">
                        {system_stats.get('memory_percent', 0)}%
                    </div>
                    <div class="stat-label">Memory Usage</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-value">
                        {system_stats.get('active_connections', 0)}
                    </div>
                    <div class="stat-label">Active Connections</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-value">
                        {len(entries)}
                    </div>
                    <div class="stat-label">Log Entries</div>
                </div>
            </div>
        </div>
    </div>
    """
    
    # Create RAG performance summary
    performance_html = f"""
    <div class="card">
        <div class="card-header">
            RAG Performance Summary
        </div>
        <div class="card-body">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value">
                        {format_time(summary.get('avg_total_time', 0))}
                    </div>
                    <div class="stat-label">Avg Total Time</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-value">
                        {format_time(summary.get('avg_gpt_time', 0))}
                    </div>
                    <div class="stat-label">Avg GPT Time</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-value">
                        {format_time(summary.get('avg_retrieval_time', 0))}
                    </div>
                    <div class="stat-label">Avg Retrieval Time</div>
                </div>
                
                <div class="stat-card">
                    <div class="stat-value">
                        {summary.get('avg_gpt_time', 0) / max(summary.get('avg_total_time', 1), 0.001) * 100:.1f}%
                    </div>
                    <div class="stat-label">GPT % of Total</div>
                </div>
            </div>
        </div>
    </div>
    """
    
    # Create log entries table
    logs_html = """
    <div class="card">
        <div class="card-header">
            Log Entries
    """
    
    # Add count of entries shown
    if entries:
        logs_html += f"""
            <span class="badge badge-success">{len(entries)} entries</span>
        """
    else:
        logs_html += """
            <span class="badge badge-warning">No entries found</span>
        """
        
    logs_html += """
        </div>
        <div class="card-body">
    """
    
    # If no entries found
    if not entries:
        logs_html += """
            <div class="no-data">
                <p>No log entries found. Try adjusting your filters or check if the log file exists.</p>
            </div>
        """
    else:
        # Build table for entries
        logs_html += """
            <div style="overflow-x: auto;">
                <table>
                    <thead>
                        <tr>
                            <th>Timestamp</th>
                            <th>Query</th>
                            <th>Times</th>
                            <th>Details</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        # Add each log entry to table
        for entry in entries:
            # Get timestamp with fallback
            timestamp = entry.get("timestamp", "N/A")
            if timestamp != "N/A":
                try:
                    # Format timestamp if it's a valid ISO date
                    dt = datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
                except (ValueError, TypeError):
                    # Keep original if we can't parse it
                    pass
            
            # Get query text with fallback
            query = entry.get("query", "")
            if len(query) > 50:
                query_display = query[:50] + "..."
            else:
                query_display = query
            
            # Get timing information with fallbacks
            timings = entry.get("timings", {})
            timings_formatted = entry.get("timings_formatted", {})
            
            total_time = timings.get("total", 0)
            total_time_formatted = timings_formatted.get("total_formatted", "N/A")
            
            # Get sources with fallback
            sources = entry.get("sources", [])
            sources_display = ", ".join([s.get("filename", "unknown") if isinstance(s, dict) else str(s) for s in sources[:3]])
            if len(sources) > 3:
                sources_display += f" + {len(sources) - 3} more"
            
            # Build the table row for this entry
            logs_html += f"""
                        <tr>
                            <td>{timestamp}</td>
                            <td>{query_display}</td>
                            <td>
                                <div>Total: {total_time_formatted}</div>
                                <div>Retrieval: {timings_formatted.get("retrieval_formatted", "N/A")}</div>
                                <div>GPT: {timings_formatted.get("gpt_formatted", "N/A")}</div>
                            </td>
                            <td>
                                <details>
                                    <summary>View Details</summary>
                                    <div style="margin-top: 0.5rem;">
                                        <h4>Query</h4>
                                        <p>{query}</p>
                                        
                                        <h4>Sources</h4>
                                        <p>{sources_display}</p>
                                        
                                        <h4>Answer</h4>
                                        <pre>{entry.get("answer", "N/A")}</pre>
                                    </div>
                                </details>
                            </td>
                        </tr>
            """
        
        # Close table
        logs_html += """
                    </tbody>
                </table>
            </div>
        """
    
    # Close logs section
    logs_html += """
        </div>
    </div>
    """
    
    # Add footer
    footer = f"""
    <div class="footer">
        <p>
            Raw data available as <a href="./debug/data?limit={limit}&filter={filter or ''}">JSON API</a>
            | Log file: {DEBUG_LOG_PATH}
        </p>
        <p>
            <a href="./">Back to Dashboard</a>
        </p>
    </div>
    """
    
    # Close container
    footer += """
    </div> <!-- end container -->
    """
    
    # Combine all HTML sections
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mobeus Assistant — Debug Logs</title>
        {css}
    </head>
    <body>
        {header_html}
        {system_stats_html}
        {performance_html}
        {logs_html}
        {footer}
    </body>
    </html>
    """
    
    return html

@router.get("/debug/data")
async def get_debug_data(
    limit: int = Query(50, description="Number of log entries to return"),
    filter: Optional[str] = Query(None, description="Filter logs by query text")
):
    """
    API endpoint to get debug data as JSON for external use.
    Provides the same debug data as the HTML dashboard but in JSON format.
    """
    try:
        entries = get_log_entries(limit=limit, filter_query=filter)
        system_stats = get_system_stats()
        
        # Calculate summaries
        summary = {
            "total_entries": float(len(entries)),
            "avg_total_time": 0.0,
            "avg_gpt_time": 0.0,
            "avg_retrieval_time": 0.0
        }
        
        if entries:
            total_times = [e.get("timings", {}).get("total", 0) for e in entries]
            gpt_times = [e.get("timings", {}).get("gpt", 0) for e in entries]
            retrieval_times = [e.get("timings", {}).get("retrieval", 0) for e in entries]
            
            summary["avg_total_time"] = sum(total_times) / max(len(total_times), 1)
            summary["avg_gpt_time"] = sum(gpt_times) / max(len(gpt_times), 1)
            summary["avg_retrieval_time"] = sum(retrieval_times) / max(len(retrieval_times), 1)
        
        return {
            "entries": entries,
            "system_stats": system_stats,
            "summary": summary
        }
    except Exception as e:
        return {
            "error": str(e),
            "entries": [],
            "system_stats": {},
            "summary": {}
        }

@router.get("/debug/sessions")
async def get_debug_sessions():
    """
    View active sessions and their metrics.
    This is a placeholder that would need integration with actual session tracking.
    """
    # This would need to be implemented with actual session tracking
    sessions = []
    
    html_content = """
    <!DOCTYPE html>
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
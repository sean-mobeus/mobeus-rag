# Enhanced tools_dashboard.py with Strategy Control
import os
import json
import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from config import DEBUG_LOG_PATH
from config import LOG_DIR

router = APIRouter()

# Tool Strategy definitions
TOOL_STRATEGIES = {
    "auto": {
        "label": "Auto", 
        "color": "blue", 
        "description": "Let AI decide when to use tools (balanced approach)"
    },
    "conservative": {
        "label": "Minimal", 
        "color": "green", 
        "description": "Prefer direct responses, minimal tool usage"
    },
    "aggressive": {
        "label": "Comprehensive", 
        "color": "purple", 
        "description": "Proactive tool usage for detailed responses"
    },
    "none": {
        "label": "Direct Only", 
        "color": "gray", 
        "description": "Never use tools, direct responses only"
    },
    "required": {
        "label": "Always Search", 
        "color": "red", 
        "description": "Always use tools before responding"
    }
}

# Path to optional separate function call logs
FUNCTION_LOG_PATH = os.path.join(LOG_DIR, os.getenv("MOBEUS_FUNCTION_LOG", "function_calls.jsonl"))
STRATEGY_LOG_PATH = os.path.join(LOG_DIR, os.getenv("MOBEUS_STRATEGY_LOG", "strategy_changes.jsonl"))

def get_function_calls(limit: int = 50, filter_query: Optional[str] = None):
    """Extract function call data from logs."""
    function_calls = []
    
    # Try to read from dedicated function log if it exists
    if os.path.exists(FUNCTION_LOG_PATH):
        try:
            with open(FUNCTION_LOG_PATH, "r") as f:
                lines = f.readlines()
                
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                    
                    # Apply filter if provided
                    if filter_query:
                        function_name = entry.get("function_name", "")
                        arguments = json.dumps(entry.get("arguments", {}))
                        
                        if (filter_query.lower() not in function_name.lower() and 
                            filter_query.lower() not in arguments.lower()):
                            continue
                    
                    function_calls.append(entry)
                    
                    if len(function_calls) >= limit:
                        break
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f"Error reading function log: {e}")
    
    # If no dedicated log, extract from debug log
    if not function_calls and os.path.exists(DEBUG_LOG_PATH):
        try:
            with open(DEBUG_LOG_PATH, "r") as f:
                lines = f.readlines()
                
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                    
                    # Look for function calls in the answer
                    answer = entry.get("answer", "")
                    if "function" in answer.lower() or "tool" in answer.lower():
                        function_name = None
                        arguments = {}
                        
                        # Try to extract function name
                        if "calling function:" in answer.lower():
                            function_part = answer.split("calling function:", 1)[1].strip()
                            function_name = function_part.split()[0].strip("'\"()[]{}").strip()
                        elif "using tool:" in answer.lower():
                            function_part = answer.split("using tool:", 1)[1].strip()
                            function_name = function_part.split()[0].strip("'\"()[]{}").strip()
                        
                        if function_name:
                            if filter_query and filter_query.lower() not in function_name.lower():
                                continue
                                
                            function_calls.append({
                                "timestamp": entry.get("timestamp", ""),
                                "query": entry.get("query", ""),
                                "function_name": function_name,
                                "arguments": arguments,
                                "result": None,
                                "execution_time": None,
                                "success": None,
                                "strategy": "unknown"
                            })
                            
                            if len(function_calls) >= limit:
                                break
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f"Error extracting function calls from debug log: {e}")
    
    # Generate sample data if no real data exists
    if not function_calls:
        function_calls = generate_sample_function_calls(limit)
    
    return function_calls

def get_strategy_changes(limit: int = 20):
    """Get recent strategy changes for analysis."""
    strategy_changes = []
    
    if os.path.exists(STRATEGY_LOG_PATH):
        try:
            with open(STRATEGY_LOG_PATH, "r") as f:
                lines = f.readlines()
                
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                    strategy_changes.append(entry)
                    if len(strategy_changes) >= limit:
                        break
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f"Error reading strategy log: {e}")
    
    return strategy_changes

def generate_sample_function_calls(count: int = 10):
    """Generate sample function call data for demonstration."""
    sample_functions = [
        "search_knowledge_base", 
        "update_user_memory", 
        "get_weather", 
        "search_web", 
        "calculate"
    ]
    
    sample_strategies = list(TOOL_STRATEGIES.keys())
    
    now = datetime.datetime.now()
    function_calls = []
    
    for i in range(count):
        idx = i % len(sample_functions)
        timestamp = (now - datetime.timedelta(minutes=i*5)).isoformat()
        success = i % 10 != 0  # 90% success rate
        
        function_calls.append({
            "timestamp": timestamp,
            "query": f"Sample query {i+1}",
            "function_name": sample_functions[idx],
            "arguments": {"query": f"Sample query {i+1}"},
            "result": {"answer": "Sample result"} if success else {"error": "Function execution failed"},
            "execution_time": (i % 5) * 0.1 + 0.1,
            "success": success,
            "strategy": sample_strategies[i % len(sample_strategies)]
        })
    
    return function_calls

def analyze_function_calls(function_calls):
    """Analyze function call data for dashboard insights."""
    if not function_calls:
        return {
            "total_calls": 0,
            "success_rate": 0,
            "function_frequency": {},
            "avg_execution_time": 0,
            "execution_times": {},
            "strategy_effectiveness": {}
        }
    
    total_calls = len(function_calls)
    successful_calls = sum(1 for call in function_calls if call.get("success", False))
    success_rate = (successful_calls / total_calls) * 100 if total_calls > 0 else 0
    
    # Analyze by function and strategy
    function_frequency = {}
    execution_times = {}
    strategy_stats = {}
    
    for call in function_calls:
        function_name = call.get("function_name", "unknown")
        strategy = call.get("strategy", "unknown")
        
        # Count function frequency
        if function_name not in function_frequency:
            function_frequency[function_name] = 0
        function_frequency[function_name] += 1
        
        # Track execution times
        execution_time = call.get("execution_time")
        if execution_time is not None:
            if function_name not in execution_times:
                execution_times[function_name] = []
            execution_times[function_name].append(execution_time)
        
        # Track strategy effectiveness
        if strategy not in strategy_stats:
            strategy_stats[strategy] = {"total": 0, "success": 0}
        strategy_stats[strategy]["total"] += 1
        if call.get("success"):
            strategy_stats[strategy]["success"] += 1
    
    # Calculate averages
    avg_execution_times = {}
    for func, times in execution_times.items():
        if times:
            avg_execution_times[func] = sum(times) / len(times)
    
    all_times = [time for times in execution_times.values() for time in times]
    avg_execution_time = sum(all_times) / len(all_times) if all_times else 0
    
    # Calculate strategy effectiveness
    strategy_effectiveness = {}
    for strategy, stats in strategy_stats.items():
        if stats["total"] > 0:
            strategy_effectiveness[strategy] = {
                "success_rate": (stats["success"] / stats["total"]) * 100,
                "total_calls": stats["total"]
            }
    
    return {
        "total_calls": total_calls,
        "success_rate": success_rate,
        "function_frequency": function_frequency,
        "avg_execution_time": avg_execution_time,
        "execution_times": avg_execution_times,
        "strategy_effectiveness": strategy_effectiveness
    }

@router.get("/tools", response_class=HTMLResponse)
async def tools_dashboard(
    request: Request,
    limit: int = Query(50, description="Number of function calls to show"),
    filter: Optional[str] = Query(None, description="Filter by function name")
):
    """Enhanced Tool/Function Calling Dashboard with Strategy Control."""
    
    function_calls = get_function_calls(limit=limit, filter_query=filter)
    strategy_changes = get_strategy_changes(limit=20)
    analysis = analyze_function_calls(function_calls)
    
    # Convert data to JSON for JavaScript
    data_json = json.dumps({
        "function_calls": function_calls,
        "strategy_changes": strategy_changes,
        "analysis": analysis,
        "strategies": TOOL_STRATEGIES
    })

    table_rows = []
    for call in function_calls:
        strategy = call.get('strategy', 'auto')
        strategy_info = TOOL_STRATEGIES.get(strategy, {'color': 'gray', 'label': strategy})
    
        table_rows.append(f"""
        <tr>
            <td>{call.get("timestamp", "")}</td>
            <td>
                <span class="strategy-badge {strategy_info['color']}">
                    {strategy_info['label']}
                </span>
            </td>
            <td>{call.get("function_name", "")}</td>
            <td>
                <span class="status-badge {'status-success' if call.get('success', False) else 'status-error'}">
                    {'Success' if call.get('success', False) else 'Error'}
                </span>
            </td>
            <td>{f"{call.get('execution_time', 0) * 1000:.1f}ms" if call.get('execution_time') is not None else "N/A"}</td>
            <td>
                <details>
                    <summary>View Details</summary>
                    <div>
                        <h3>Query</h3>
                        <p>{call.get("query", "")}</p>
                    
                        <h3>Arguments</h3>
                        <div class="code-block">{json.dumps(call.get("arguments", {}), indent=2)}</div>
                    
                        <h3>Result</h3>
                        <div class="code-block">{json.dumps(call.get("result", {}), indent=2)}</div>
                    </div>
                </details>
            </td>
        </tr>
        """)

    table_rows_html = "".join(table_rows)    
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mobeus Assistant — Tool Control Dashboard</title>
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
            
            /* Strategy Control Styles */
            .strategy-controls {{
                display: flex;
                align-items: center;
                gap: 1rem;
                margin-bottom: 1.5rem;
            }}
            
            .strategy-selector {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }}
            
            .strategy-dropdown {{
                position: relative;
            }}
            
            .strategy-button {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.5rem 1rem;
                background-color: var(--card-color);
                border: 1px solid var(--border-color);
                border-radius: 0.375rem;
                cursor: pointer;
                transition: all 0.2s;
                font-size: 0.875rem;
            }}
            
            .strategy-button:hover {{
                background-color: #f9fafb;
            }}
            
            .strategy-badge {{
                display: inline-flex;
                align-items: center;
                gap: 0.25rem;
                padding: 0.25rem 0.5rem;
                border-radius: 0.375rem;
                font-size: 0.75rem;
                font-weight: 500;
            }}
            
            .strategy-badge.blue {{ background-color: rgba(37, 99, 235, 0.1); color: #2563eb; }}
            .strategy-badge.green {{ background-color: rgba(16, 185, 129, 0.1); color: #10b981; }}
            .strategy-badge.purple {{ background-color: rgba(139, 92, 246, 0.1); color: #8b5cf6; }}
            .strategy-badge.gray {{ background-color: rgba(107, 114, 128, 0.1); color: #6b7280; }}
            .strategy-badge.red {{ background-color: rgba(239, 68, 68, 0.1); color: #ef4444; }}
            
            .strategy-menu {{
                position: fixed;
                background-color: var(--card-color);
                border: 1px solid var(--border-color);
                border-radius: 0.375rem;
                box-shadow: 0 8px 16px rgba(0, 0, 0, 0.15);
                z-index: 99999;
                display: none;
                min-width: 300px;
                max-width: 400px;
            }}
            
            .strategy-menu.show {{
                display: block;
            }}
            
            .strategy-option {{
                padding: 0.75rem;
                cursor: pointer;
                border-bottom: 1px solid var(--border-color);
                transition: background-color 0.2s;
            }}
            
            .strategy-option:last-child {{
                border-bottom: none;
            }}
            
            .strategy-option:hover {{
                background-color: #f9fafb;
            }}
            
            .strategy-option.active {{
                background-color: var(--primary-light);
            }}
            
            .strategy-title {{
                font-weight: 500;
                margin-bottom: 0.25rem;
            }}
            
            .strategy-description {{
                font-size: 0.75rem;
                color: #6b7280;
            }}
            
            .current-strategy {{
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.75rem 1rem;
                background-color: var(--primary-light);
                border-radius: 0.375rem;
                font-size: 0.875rem;
            }}
            
            .status-indicator {{
                width: 8px;
                height: 8px;
                border-radius: 50%;
                background-color: var(--good-color);
                animation: pulse 2s infinite;
            }}
            
            @keyframes pulse {{
                0%, 100% {{ opacity: 1; }}
                50% {{ opacity: 0.5; }}
            }}
            
            /* Rest of existing styles */
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
            
            .status-badge {{
                display: inline-block;
                padding: 0.25rem 0.5rem;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 500;
            }}
            
            .status-success {{
                background-color: rgba(16, 185, 129, 0.1);
                color: #10b981;
            }}
            
            .status-error {{
                background-color: rgba(239, 68, 68, 0.1);
                color: #ef4444;
            }}
            
            .code-block {{
                background-color: var(--code-bg);
                border-radius: 0.375rem;
                padding: 0.75rem;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 0.875rem;
                white-space: pre-wrap;
                overflow-wrap: break-word;
                max-height: 200px;
                overflow-y: auto;
            }}
            
            .good {{ color: var(--good-color); }}
            .warning {{ color: var(--warning-color); }}
            .bad {{ color: var(--bad-color); }}
            
            details {{
                margin-top: 0.5rem;
            }}
            
            summary {{
                cursor: pointer;
                margin-bottom: 0.5rem;
                font-weight: 500;
            }}
            
            @media (max-width: 768px) {{
                .strategy-controls {{
                    flex-direction: column;
                    align-items: stretch;
                }}
                
                .grid-layout {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="dashboard">
            <div class="breadcrumb">
                <a href="/admin/">Dashboard</a>
                <span>/</span>
                <span>Tool Control</span>
            </div>
            
            <div class="header">
                <h1>🎛️ Mobeus Assistant — Tool Control Dashboard</h1>
            </div>
            
            <!-- Strategy Control Section -->
            <div class="card">
                <div class="card-header">
                    Tool Strategy Control
                    <span class="status-indicator" id="connection-status"></span>
                </div>
                <div class="card-body">
                    <div class="strategy-controls">
                        <div class="strategy-selector">
                            <label for="strategy-select" style="font-weight: 500; margin-right: 0.5rem;">AI Tool Strategy:</label>
                            <div class="strategy-dropdown">
                                <button class="strategy-button" id="strategy-button" onclick="toggleStrategyMenu()">
                                    <span class="strategy-badge blue" id="current-strategy-badge">
                                        <span id="current-strategy-label">Auto</span>
                                    </span>
                                    <svg width="16" height="16" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" clip-rule="evenodd"/>
                                    </svg>
                                </button>
                                <div class="strategy-menu" id="strategy-menu">
                                    <!-- Strategy options will be populated by JavaScript -->
                                </div>
                            </div>
                        </div>
                        
                        <div class="current-strategy" id="current-strategy-info">
                            <div class="status-indicator"></div>
                            <span>Current strategy will adapt AI tool usage behavior</span>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Analytics Section -->
            <div class="card">
                <div class="card-header">
                    Tool Usage Analytics
                </div>
                <div class="card-body">
                    <div class="metrics-grid">
                        <div class="metric">
                            <div class="metric-value">{analysis["total_calls"]}</div>
                            <div class="metric-label">Total Tool Calls</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value {
                                'good' if analysis["success_rate"] >= 95 else
                                'warning' if analysis["success_rate"] >= 80 else
                                'bad'
                            }">{analysis["success_rate"]:.1f}%</div>
                            <div class="metric-label">Success Rate</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{analysis["avg_execution_time"] * 1000:.1f}ms</div>
                            <div class="metric-label">Avg Execution Time</div>
                        </div>
                        <div class="metric">
                            <div class="metric-value">{len(analysis["function_frequency"])}</div>
                            <div class="metric-label">Unique Tools Used</div>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="grid-layout">
                <div class="card">
                    <div class="card-header">
                        Tool Usage by Strategy
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="strategyEffectivenessChart"></canvas>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        Tool Success Rates
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="functionSuccessChart"></canvas>
                        </div>
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    Recent Tool Calls
                    <span>{len(function_calls)} calls</span>
                </div>
                <div class="card-body">
                    <div class="table-container">
                        <table>
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Strategy</th>
                                    <th>Function</th>
                                    <th>Status</th>
                                    <th>Execution Time</th>
                                    <th>Details</th>
                                </tr>
                            </thead>
                            <tbody>
                                {table_rows_html}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        

        <script>
        // Parse dashboard data
        const dashboardData = {data_json};
        let currentStrategy = 'auto';

        // WebSocket connection for real-time updates
        let dashboardSocket = null;
        let isConnected = false;

        // Initialize dashboard WebSocket connection
        function initializeDashboardWebSocket() {{
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${{protocol}}//${{window.location.host}}/chat/admin/dashboard`;
    
            console.log('🔗 Connecting dashboard WebSocket:', wsUrl);
    
            dashboardSocket = new WebSocket(wsUrl);
    
            dashboardSocket.onopen = function(event) {{
                console.log('✅ Dashboard WebSocket connected');
                isConnected = true;
                updateConnectionStatus(true);
            }};
    
            dashboardSocket.onmessage = function(event) {{
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            }};
    
            dashboardSocket.onclose = function(event) {{
                console.log('🔌 Dashboard WebSocket disconnected');
                isConnected = false;
                updateConnectionStatus(false);
        
                // Attempt to reconnect after 3 seconds
                setTimeout(initializeDashboardWebSocket, 3000);
            }};
    
            dashboardSocket.onerror = function(error) {{
                console.error('❌ Dashboard WebSocket error:', error);
                isConnected = false;
                updateConnectionStatus(false);
            }};
        }}

        // Handle WebSocket messages
        function handleWebSocketMessage(data) {{
            console.log('📨 Dashboard received:', data.type, data);
    
            switch(data.type) {{
                case 'session_status':
                    updateSessionStatus(data);
                    break;
            
                case 'session_connected':
                    showNotification(`New voice session connected (Strategy: ${{data.strategy}})`, 'success');
                    updateSessionCount(data.total_sessions);
                    break;
            
                case 'session_disconnected':
                    showNotification('Voice session disconnected', 'info');
                    updateSessionCount(data.total_sessions);
                    break;
            
                case 'broadcast_confirmed':
                    showNotification(`Strategy broadcast successful! ${{data.sessions_updated}} sessions updated to '${{data.strategy}}'`, 'success');
                    break;
            
                case 'strategy_broadcast_completed':
                    if (data.sessions_updated > 0) {{
                        showNotification(`${{data.sessions_updated}} voice sessions updated to '${{data.new_strategy}}'`, 'success');
                    }}
                    break;
            
                default:
                    console.log('📨 Unhandled message type:', data.type);
            }}
        }}

        // Update connection status indicator
        function updateConnectionStatus(connected) {{
            const indicator = document.getElementById('connection-status');
            if (indicator) {{
                indicator.style.backgroundColor = connected ? '#10b981' : '#ef4444';
                indicator.title = connected ? 'Connected to live sessions' : 'Disconnected';
            }}
        }}

        // Update session count display
        function updateSessionCount(count) {{
            const statusElement = document.getElementById('current-strategy-info');
            if (statusElement) {{
                statusElement.innerHTML = `
                    <div class="status-indicator"></div>
                    <span>${{count}} active voice session${{count !== 1 ? 's' : ''}}</span>
                `;
            }}
        }}

        // Update session status from WebSocket
        function updateSessionStatus(data) {{
            console.log('📊 Session status:', data);
            updateSessionCount(data.total_sessions);
    
            // Update any session-specific UI elements here
            if (data.active_sessions && data.active_sessions.length > 0) {{
                const latestSession = data.active_sessions[data.active_sessions.length - 1];
                if (latestSession.strategy !== currentStrategy) {{
                    // Update UI to reflect the strategy of the most recent session
                    updateCurrentStrategy(latestSession.strategy);
                }}
            }}
        }}

        // Send strategy broadcast to all voice sessions
        function sendStrategyBroadcast(strategy) {{
            if (!isConnected || !dashboardSocket) {{
                showNotification('Not connected to voice sessions!', 'error');
                return false;
            }}
    
            const message = {{
                type: 'broadcast_strategy_update',
                strategy: strategy,
                timestamp: new Date().toISOString()
            }};
    
            dashboardSocket.send(JSON.stringify(message));
            console.log('📡 Broadcasting strategy update:', strategy);
    
            // Show immediate feedback
            showNotification(`Broadcasting strategy change to all voice sessions...`, 'info');
            return true;
        }}

        // Show notification to user
        function showNotification(message, type = 'info') {{
            const notification = document.createElement('div');
            notification.className = `notification notification-${{type}}`;
            notification.innerHTML = `
                <div class="notification-content">
                    <span>${{message}}</span>
                    <button onclick="this.parentElement.parentElement.remove()">×</button>
                </div>
            `;
    
            // Add to page
            document.body.appendChild(notification);
    
            // Auto-remove after 5 seconds
            setTimeout(() => {{
                if (notification.parentElement) {{
                    notification.remove();
                }}
            }}, 5000);
        }}

        // Initialize strategy dropdown
        function initializeStrategyControls() {{
            console.log('🔧 Initializing strategy controls...');
    
            const menuElement = document.getElementById('strategy-menu');
            console.log('Menu element found:', menuElement);
    
            const strategies = dashboardData.strategies;
            console.log('Strategies object:', strategies);
    
            if (!strategies) {{
                console.error('❌ No strategies found in dashboardData');
                return;
            }}
    
            // Clear existing options
            menuElement.innerHTML = '';
    
            Object.entries(strategies).forEach(([key, strategy]) => {{
                console.log(`Adding strategy: ${{key}}`, strategy);
                const option = document.createElement('div');
                option.className = 'strategy-option';
                option.dataset.strategy = key;
                option.innerHTML = `
                    <div class="strategy-title">
                        <span class="strategy-badge ${{strategy.color}}">${{strategy.label}}</span>
                    </div>
                    <div class="strategy-description">${{strategy.description}}</div>
                `;
                option.onclick = () => selectStrategy(key);
                menuElement.appendChild(option);
            }});
    
            console.log('✅ Strategy controls initialized');
            updateCurrentStrategy(currentStrategy);
        }}

        function toggleStrategyMenu() {{
            const menu = document.getElementById('strategy-menu');
            const button = document.getElementById('strategy-button');
    
            console.log('🔽 Toggle menu clicked, current classes:', menu.className);
    
            if (menu.classList.contains('show')) {{
                menu.classList.remove('show');
            }} else {{
                // Position the menu relative to the button
                const buttonRect = button.getBoundingClientRect();
                menu.style.top = (buttonRect.bottom + 5) + 'px';
                menu.style.left = buttonRect.left + 'px';
                menu.classList.add('show');
            }}
    
            console.log('🔽 After toggle, classes:', menu.className);
        }}

        function selectStrategy(strategyKey) {{
            console.log('🎛️ Strategy selected:', strategyKey);
    
            currentStrategy = strategyKey;
            updateCurrentStrategy(strategyKey);
    
            // Send strategy broadcast to all voice sessions
            const success = sendStrategyBroadcast(strategyKey);
            
            // Close menu
            document.getElementById('strategy-menu').classList.remove('show');
    
            if (success) {{
                // Show immediate visual feedback
                const button = document.getElementById('strategy-button');
                button.style.backgroundColor = '#10b981';
                setTimeout(() => {{
                    button.style.backgroundColor = '';
                }}, 1000);
            }}
        }}

        function updateCurrentStrategy(strategyKey) {{
            const strategy = dashboardData.strategies[strategyKey];
            if (!strategy) return;
    
            // Update button
            const badge = document.getElementById('current-strategy-badge');
            const label = document.getElementById('current-strategy-label');
    
            if (badge && label) {{
                badge.className = `strategy-badge ${{strategy.color}}`;
                label.textContent = strategy.label;
            }}
    
            // Update info text
            const info = document.getElementById('current-strategy-info');
            if (info && !info.innerHTML.includes('active voice session')) {{
                info.innerHTML = `
                    <div class="status-indicator"></div>
                    <span>${{strategy.description}}</span>
                `;
            }}
    
            // Update active state in menu
            document.querySelectorAll('.strategy-option').forEach(option => {{
                option.classList.toggle('active', option.dataset.strategy === strategyKey);
            }});
        }}

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {{
            if (!e.target.closest('.strategy-dropdown')) {{
                document.getElementById('strategy-menu').classList.remove('show');
            }}
        }});

        // Initialize charts
        function initializeCharts() {{
            // Strategy Effectiveness Chart
            const strategyCtx = document.getElementById('strategyEffectivenessChart').getContext('2d');
            const strategyData = dashboardData.analysis.strategy_effectiveness || {{}};
    
            new Chart(strategyCtx, {{
                type: 'bar',
                data: {{
                    labels: Object.keys(strategyData),
                    datasets: [{{
                        label: 'Success Rate (%)',
                        data: Object.values(strategyData).map(s => s.success_rate || 0),
                        backgroundColor: '#3b82f6',
                        borderColor: '#2563eb',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{ display: false }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            max: 100,
                            title: {{
                                display: true,
                                text: 'Success Rate (%)'
                            }}
                        }},
                    }}
                }}
            }});
    
            // Function Success Chart
            const functionCtx = document.getElementById('functionSuccessChart').getContext('2d');
            const functionFreq = dashboardData.analysis.function_frequency || {{}};
    
            new Chart(functionCtx, {{
                type: 'doughnut',
                data: {{
                    labels: Object.keys(functionFreq),
                    datasets: [{{
                        data: Object.values(functionFreq),
                        backgroundColor: [
                            '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6'
                        ]
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            position: 'bottom'
                        }}
                    }}
                }}
            }});
        }}

        // Initialize everything when DOM is loaded
        document.addEventListener('DOMContentLoaded', () => {{
            initializeStrategyControls();
            initializeCharts();
            initializeDashboardWebSocket();
        }});

        // Add notification styles
        const notificationStyles = `
            .notification {{
                position: fixed;
                top: 20px;
                right: 20px;
                min-width: 300px;
                max-width: 500px;
                padding: 1rem;
                border-radius: 0.5rem;
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                z-index: 10000;
                animation: slideIn 0.3s ease-out;
            }}
    
            .notification-success {{
                background-color: #d1fae5;
                border: 1px solid #10b981;
                color: #065f46;
            }}
    
            .notification-error {{
                background-color: #fee2e2;
                border: 1px solid #ef4444;
                color: #991b1b;
            }}
    
            .notification-info {{
                background-color: #dbeafe;
                border: 1px solid #3b82f6;
                color: #1e40af;
            }}
    
            .notification-content {{
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
    
            .notification button {{
                background: none;
                border: none;
                font-size: 1.2rem;
                cursor: pointer;
                padding: 0;
                margin-left: 1rem;
            }}
    
            @keyframes slideIn {{
                from {{
                    transform: translateX(100%);
                    opacity: 0;
                }}
                to {{
                    transform: translateX(0);
                    opacity: 1;
                }}
            }}
        `;

        // Inject notification styles
        const styleSheet = document.createElement('style');
        styleSheet.textContent = notificationStyles;
        document.head.appendChild(styleSheet);
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

def log_strategy_change(user_uuid: str, old_strategy: str, new_strategy: str):
    """Log strategy changes for analysis."""
    with open(STRATEGY_LOG_PATH, "a") as f:
        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "user_uuid": user_uuid,
            "old_strategy": old_strategy,
            "new_strategy": new_strategy,
            "type": "strategy_change"
        }
        f.write(json.dumps(entry) + "\n")

@router.get("/tools/data")
async def get_tools_data(
    limit: int = Query(50, description="Number of function calls to return"),
    filter: Optional[str] = Query(None, description="Filter by function name")
):
    """API endpoint to get function call data as JSON for external use."""
    function_calls = get_function_calls(limit=limit, filter_query=filter)
    strategy_changes = get_strategy_changes(limit=20)
    analysis = analyze_function_calls(function_calls)
    
    return JSONResponse({
        "function_calls": function_calls,
        "strategy_changes": strategy_changes,
        "analysis": analysis,
        "strategies": TOOL_STRATEGIES
    })
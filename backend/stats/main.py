# tools_dashboard.py
import os
import json
import datetime
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from config import DEBUG_LOG_PATH

router = APIRouter()

# Path to optional separate function call logs
FUNCTION_LOG_PATH = os.getenv("MOBEUS_FUNCTION_LOG", "function_calls.jsonl")

def get_function_calls(limit: int = 50, filter_query: Optional[str] = None):
    """
    Extract function call data from logs.
    In a production system, this would be tied to a database of function calls.
    Here we're simulating with a file-based approach.
    """
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
                        # Filter by function name or arguments
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
    
    # If no dedicated log or no entries found, extract from debug log
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
                        # Extract function call details from the answer using simple heuristics
                        # This is a simplified approach - in a real system, you'd have structured logs
                        function_name = None
                        arguments = {}
                        
                        # Try to extract function name
                        if "calling function:" in answer.lower():
                            function_part = answer.split("calling function:", 1)[1].strip()
                            function_name = function_part.split()[0].strip("'\"()[]{}").strip()
                        elif "using tool:" in answer.lower():
                            function_part = answer.split("using tool:", 1)[1].strip()
                            function_name = function_part.split()[0].strip("'\"()[]{}").strip()
                        
                        # If we found a function name, create an entry
                        if function_name:
                            # Apply filter if provided
                            if filter_query and filter_query.lower() not in function_name.lower():
                                continue
                                
                            function_calls.append({
                                "timestamp": entry.get("timestamp", ""),
                                "query": entry.get("query", ""),
                                "function_name": function_name,
                                "arguments": arguments,  # This would be empty with our simple parsing
                                "result": None,  # We don't have the result in this simple extraction
                                "execution_time": None,
                                "success": None
                            })
                            
                            if len(function_calls) >= limit:
                                break
                except json.JSONDecodeError:
                    continue
        except Exception as e:
            print(f"Error extracting function calls from debug log: {e}")
    
    # If still no data, generate sample data for demonstration
    if not function_calls:
        # Generate sample data for demonstration purposes
        function_calls = generate_sample_function_calls(limit)
    
    return function_calls

def generate_sample_function_calls(count: int = 10):
    """Generate sample function call data for demonstration."""
    sample_functions = [
        "search_knowledge_base", 
        "update_user_memory", 
        "get_weather", 
        "search_web", 
        "calculate"
    ]
    
    sample_arguments = [
        {"query": "How does RAG work?"},
        {"information": "User prefers concise answers", "user_uuid": "user123"},
        {"location": "San Francisco"},
        {"query": "latest AI research"},
        {"expression": "2 + 2 * 4"}
    ]
    
    sample_results = [
        {"answer": "RAG (Retrieval Augmented Generation) works by...", "sources": ["doc1.md", "doc2.md"]},
        {"success": True, "message": "User memory updated"},
        {"temperature": 72, "conditions": "Sunny", "forecast": "Clear skies"},
        {"results": ["Result 1", "Result 2"], "source": "web"},
        {"result": 10, "steps": ["Multiply: 2*4=8", "Add: 2+8=10"]}
    ]
    
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
            "arguments": sample_arguments[idx],
            "result": sample_results[idx] if success else {"error": "Function execution failed"},
            "execution_time": (i % 5) * 0.1 + 0.1,  # 0.1 to 0.5 seconds
            "success": success
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
            "execution_times": {}
        }
    
    total_calls = len(function_calls)
    successful_calls = sum(1 for call in function_calls if call.get("success", False))
    success_rate = (successful_calls / total_calls) * 100 if total_calls > 0 else 0
    
    # Analyze execution times and frequency by function
    function_frequency = {}
    execution_times = {}
    function_success = {}
    
    for call in function_calls:
        function_name = call.get("function_name", "unknown")
        
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
        
        # Track success rates
        success = call.get("success")
        if success is not None:
            if function_name not in function_success:
                function_success[function_name] = {"success": 0, "total": 0}
            function_success[function_name]["total"] += 1
            if success:
                function_success[function_name]["success"] += 1
    
    # Calculate average execution times
    avg_execution_times = {}
    for func, times in execution_times.items():
        if times:
            avg_execution_times[func] = sum(times) / len(times)
    
    # Calculate overall average execution time
    all_times = [time for times in execution_times.values() for time in times]
    avg_execution_time = sum(all_times) / len(all_times) if all_times else 0
    
    # Calculate function success rates
    function_success_rates = {}
    for func, data in function_success.items():
        if data["total"] > 0:
            function_success_rates[func] = (data["success"] / data["total"]) * 100
    
    return {
        "total_calls": total_calls,
        "success_rate": success_rate,
        "function_frequency": function_frequency,
        "avg_execution_time": avg_execution_time,
        "execution_times": avg_execution_times,
        "function_success_rates": function_success_rates
    }

@router.get("/tools", response_class=HTMLResponse)
async def tools_dashboard(
    request: Request,
    limit: int = Query(50, description="Number of function calls to show"),
    filter: Optional[str] = Query(None, description="Filter by function name")
):
    """
    Tool/Function Calling Dashboard for monitoring and debugging API tool usage.
    """
    function_calls = get_function_calls(limit=limit, filter_query=filter)
    analysis = analyze_function_calls(function_calls)
    
    # Convert data to JSON for JavaScript
    data_json = json.dumps({
        "function_calls": function_calls,
        "analysis": analysis
    })
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mobeus Assistant — Tool Calling Dashboard</title>
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
            
            .filters {{
                background-color: var(--card-color);
                border-radius: 0.5rem;
                padding: 1rem;
                margin-bottom: 1.5rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }}
            
            .filters form {{
                display: flex;
                flex-wrap: wrap;
                gap: 1rem;
                align-items: flex-end;
            }}
            
            .filters .form-group {{
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
            }}
            
            .filters label {{
                font-size: 0.875rem;
                font-weight: 500;
            }}
            
            .filters input, .filters select {{
                padding: 0.5rem;
                border: 1px solid var(--border-color);
                border-radius: 0.375rem;
                font-size: 0.875rem;
            }}
            
            .filters button {{
                padding: 0.5rem 1rem;
                background-color: var(--primary-color);
                color: white;
                border: none;
                border-radius: 0.375rem;
                font-weight: 500;
                cursor: pointer;
                height: 38px;
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
            
            .good {{
                color: var(--good-color);
            }}
            
            .warning {{
                color: var(--warning-color);
            }}
            
            .bad {{
                color: var(--bad-color);
            }}
            
            details {{
                margin-top: 0.5rem;
            }}
            
            summary {{
                cursor: pointer;
                margin-bottom: 0.5rem;
                font-weight: 500;
            }}
            
            @media (max-width: 768px) {{
                .grid-layout {{
                    grid-template-columns: 1fr;
                }}
                
                .filters form {{
                    flex-direction: column;
                    align-items: stretch;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="dashboard">
            <div class="header">
                <h1>Mobeus Assistant — Tool Calling Dashboard</h1>
            </div>
            
            <div class="filters card">
                <form method="GET" action="/tools">
                    <div class="form-group">
                        <label for="limit">Max Entries</label>
                        <input type="number" id="limit" name="limit" value="{limit}" min="1" max="1000">
                    </div>
                    
                    <div class="form-group">
                        <label for="filter">Filter Function</label>
                        <input type="text" id="filter" name="filter" value="{filter or ''}" placeholder="Function name...">
                    </div>
                    
                    <button type="submit">Apply Filters</button>
                </form>
            </div>
            
            <div class="card">
                <div class="card-header">
                    Tool Call Summary
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
                        Tool Usage Frequency
                    </div>
                    <div class="card-body">
                        <div class="chart-container">
                            <canvas id="functionFrequencyChart"></canvas>
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
                    Tool Execution Times
                </div>
                <div class="card-body">
                    <div class="chart-container">
                        <canvas id="executionTimeChart"></canvas>
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
                                    <th>Function</th>
                                    <th>Status</th>
                                    <th>Execution Time</th>
                                    <th>Details</th>
                                </tr>
                            </thead>
                            <tbody>
                                {"".join([f"""
                                <tr>
                                    <td>{call.get("timestamp", "")}</td>
                                    <td>{call.get("function_name", "")}</td>
                                    <td>
                                        <span class="status-badge {
                                            'status-success' if call.get('success', False) else 'status-error'
                                        }">
                                            {
                                                'Success' if call.get('success', False) else 'Error'
                                            }
                                        </span>
                                    </td>
                                    <td>{
                                        f"{call.get('execution_time', 0) * 1000:.1f}ms" 
                                        if call.get('execution_time') is not None else "N/A"
                                    }</td>
                                    <td>
                                        <details>
                                            <summary>View Details</summary>
                                            <div>
                                                <h3>Query</h3>
                                                <p>{call.get("query", "")}</p>
                                                
                                                <h3>Arguments</h3>
                                                <div class="code-block">{
                                                    json.dumps(call.get("arguments", {}), indent=2)
                                                }</div>
                                                
                                                <h3>Result</h3>
                                                <div class="code-block">{
                                                    json.dumps(call.get("result", {}), indent=2)
                                                }</div>
                                            </div>
                                        </details>
                                    </td>
                                </tr>
                                """ for call in function_calls])}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Parse data
            const dashboardData = {data_json};
            
            // Function Frequency Chart
            const functionFrequencyCtx = document.getElementById('functionFrequencyChart').getContext('2d');
            const functionNames = Object.keys(dashboardData.analysis.function_frequency);
            const functionCounts = Object.values(dashboardData.analysis.function_frequency);
            
            new Chart(functionFrequencyCtx, {{
                type: 'bar',
                data: {{
                    labels: functionNames,
                    datasets: [{{
                        label: 'Number of Calls',
                        data: functionCounts,
                        backgroundColor: '#3b82f6',
                        borderColor: '#2563eb',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            display: false
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            title: {{
                                display: true,
                                text: 'Number of Calls'
                            }}
                        }}
                    }}
                }}
            }});
            
            // Function Success Rate Chart
            const functionSuccessCtx = document.getElementById('functionSuccessChart').getContext('2d');
            const functionSuccessRates = dashboardData.analysis.function_success_rates || {{}};
            const successRateLabels = Object.keys(functionSuccessRates);
            const successRateValues = Object.values(functionSuccessRates);
            
            new Chart(functionSuccessCtx, {{
                type: 'bar',
                data: {{
                    labels: successRateLabels,
                    datasets: [{{
                        label: 'Success Rate (%)',
                        data: successRateValues,
                        backgroundColor: successRateValues.map(rate => 
                            rate >= 95 ? '#10b981' : 
                            rate >= 80 ? '#f59e0b' : 
                            '#ef4444'
                        ),
                        borderColor: successRateValues.map(rate => 
                            rate >= 95 ? '#059669' : 
                            rate >= 80 ? '#d97706' : 
                            '#dc2626'
                        ),
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            display: false
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            max: 100,
                            title: {{
                                display: true,
                                text: 'Success Rate (%)'
                            }}
                        }}
                    }}
                }}
            }});
            
            // Execution Time Chart
            const executionTimeCtx = document.getElementById('executionTimeChart').getContext('2d');
            const executionTimes = dashboardData.analysis.execution_times || {{}};
            const executionTimeLabels = Object.keys(executionTimes);
            const executionTimeValues = Object.values(executionTimes).map(time => time * 1000); // Convert to ms
            
            new Chart(executionTimeCtx, {{
                type: 'bar',
                data: {{
                    labels: executionTimeLabels,
                    datasets: [{{
                        label: 'Execution Time (ms)',
                        data: executionTimeValues,
                        backgroundColor: '#8b5cf6',
                        borderColor: '#7c3aed',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        legend: {{
                            display: false
                        }}
                    }},
                    scales: {{
                        y: {{
                            beginAtZero: true,
                            title: {{
                                display: true,
                                text: 'Average Execution Time (ms)'
                            }}
                        }}
                    }}
                }}
            }});
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

@router.get("/tools/data")
async def get_tools_data(
    limit: int = Query(50, description="Number of function calls to return"),
    filter: Optional[str] = Query(None, description="Filter by function name")
):
    """
    API endpoint to get function call data as JSON for external use.
    """
    function_calls = get_function_calls(limit=limit, filter_query=filter)
    analysis = analyze_function_calls(function_calls)
    
    return JSONResponse({
        "function_calls": function_calls,
        "analysis": analysis
    })
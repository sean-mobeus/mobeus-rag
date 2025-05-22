# rag_dashboard.py
import os
import json
import datetime
import statistics
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, JSONResponse
from config import DEBUG_LOG_PATH

router = APIRouter()

def get_rag_performance_data(limit: int = 100, filter_query: Optional[str] = None):
    """
    Extract RAG-specific performance data from the debug log file.
    
    Args:
        limit: Maximum number of entries to analyze
        filter_query: Optional string to filter entries
        
    Returns:
        Dictionary of RAG performance metrics
    """
    entries = []
    
    try:
        if not os.path.exists(DEBUG_LOG_PATH):
            return {"error": "Debug log file not found", "entries": []}
            
        with open(DEBUG_LOG_PATH, "r") as f:
            lines = f.readlines()
            
        for line in reversed(lines):
            try:
                entry = json.loads(line)
                
                # Apply filter if provided
                if filter_query and filter_query.lower() not in entry.get("query", "").lower():
                    continue
                
                entries.append(entry)
                
                if len(entries) >= limit:
                    break
            except json.JSONDecodeError:
                continue
    except Exception as e:
        return {"error": f"Error reading log file: {e}", "entries": []}
    
    # Calculate RAG-specific metrics
    total_entries = len(entries)
    if total_entries == 0:
        return {"error": "No entries found", "entries": []}
    
    # Extract retrieval times
    retrieval_times = [entry.get("timings", {}).get("retrieval", 0) for entry in entries]
    
    # Calculate metrics for retrieved chunks
    chunk_counts = []
    chunk_scores = []
    source_frequency = {}
    
    for entry in entries:
        chunks = entry.get("top_chunks", [])
        chunk_counts.append(len(chunks))
        
        for chunk in chunks:
            # Extract score if available
            if "score" in chunk:
                chunk_scores.append(chunk["score"])
            
            # Count sources
            source = chunk.get("source", "unknown")
            source_frequency[source] = source_frequency.get(source, 0) + 1
    
    # Calculate average chunks per query
    avg_chunks = sum(chunk_counts) / total_entries if chunk_counts else 0
    
    # Calculate score metrics
    score_metrics = {}
    if chunk_scores:
        score_metrics = {
            "min_score": min(chunk_scores),
            "max_score": max(chunk_scores),
            "avg_score": sum(chunk_scores) / len(chunk_scores),
            "median_score": statistics.median(chunk_scores) if len(chunk_scores) > 0 else 0
        }
    
    # Sort sources by frequency
    top_sources = sorted(source_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "entries": entries,
        "total_entries": total_entries,
        "retrieval_times": {
            "min": min(retrieval_times),
            "max": max(retrieval_times),
            "avg": sum(retrieval_times) / total_entries,
            "median": statistics.median(retrieval_times) if len(retrieval_times) > 0 else 0
        },
        "chunks": {
            "min": min(chunk_counts) if chunk_counts else 0,
            "max": max(chunk_counts) if chunk_counts else 0,
            "avg": avg_chunks,
            "total": sum(chunk_counts) if chunk_counts else 0
        },
        "scores": score_metrics,
        "top_sources": top_sources
    }

def analyze_query_length_vs_retrieval_time(entries):
    """Analyze relationship between query length and retrieval time"""
    data = []
    for entry in entries:
        query = entry.get("query", "")
        retrieval_time = entry.get("timings", {}).get("retrieval", 0)
        
        if query and retrieval_time > 0:
            data.append({
                "query_length": len(query),
                "retrieval_time": retrieval_time,
                "query": query
            })
    
    return data

def analyze_source_relevance(entries):
    """Analyze which sources are most relevant for different query types"""
    query_source_map = {}
    
    for entry in entries:
        query = entry.get("query", "")
        chunks = entry.get("top_chunks", [])
        
        if not query or not chunks:
            continue
            
        # Classify query (simple approach - can be made more sophisticated)
        query_type = "general"
        if "how" in query.lower():
            query_type = "how_to"
        elif "what" in query.lower():
            query_type = "definition"
        elif "?" in query:
            query_type = "question"
        
        if query_type not in query_source_map:
            query_source_map[query_type] = {}
        
        for chunk in chunks:
            source = chunk.get("source", "unknown")
            score = chunk.get("score", 0)
            
            if source not in query_source_map[query_type]:
                query_source_map[query_type][source] = {
                    "count": 0,
                    "total_score": 0,
                    "example_queries": []
                }
            
            query_source_map[query_type][source]["count"] += 1
            query_source_map[query_type][source]["total_score"] += score
            
            # Store a few example queries for each source
            if len(query_source_map[query_type][source]["example_queries"]) < 3:
                query_source_map[query_type][source]["example_queries"].append(query)
    
    # Calculate average score for each source per query type
    for query_type, sources in query_source_map.items():
        for source, data in sources.items():
            data["avg_score"] = data["total_score"] / data["count"] if data["count"] > 0 else 0
    
    return query_source_map

@router.get("/rag", response_class=HTMLResponse)
async def rag_dashboard(
    request: Request,
    limit: int = Query(100, description="Number of log entries to analyze"),
    filter: Optional[str] = Query(None, description="Filter by query text")
):
    """
    RAG performance dashboard with in-depth analysis and visualizations.
    """
    rag_data = get_rag_performance_data(limit=limit, filter_query=filter)
    
    if "error" in rag_data and rag_data.get("entries", []) == []:
        return HTMLResponse(f"""
        <html>
        <head>
            <title>Mobeus Assistant — RAG Analysis Dashboard</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                    padding: 2rem;
                    line-height: 1.5;
                }}
                
                .error-container {{
                    max-width: 600px;
                    margin: 4rem auto;
                    padding: 2rem;
                    background-color: #fee2e2;
                    border: 1px solid #ef4444;
                    border-radius: 0.5rem;
                    text-align: center;
                }}
                
                h1 {{
                    margin-bottom: 1rem;
                    color: #b91c1c;
                }}
            </style>
        </head>
        <body>
            <div class="error-container">
                <h1>Error Loading RAG Data</h1>
                <p>{rag_data.get("error", "Unknown error")}</p>
            </div>
        </body>
        </html>
        """)
    
    # Further analyze the data
    entries = rag_data["entries"]
    query_length_data = analyze_query_length_vs_retrieval_time(entries)
    source_relevance_data = analyze_source_relevance(entries)
    
    # Convert data to JSON for JavaScript
    rag_data_json = json.dumps({
        "retrieval_times": rag_data["retrieval_times"],
        "chunks": rag_data["chunks"],
        "scores": rag_data.get("scores", {}),
        "top_sources": rag_data["top_sources"],
        "query_length_data": query_length_data,
        "source_relevance_data": source_relevance_data
    })
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mobeus Assistant — RAG Analysis Dashboard</title>
        <script src="https://cdn.jsdelivr.net/npm/chart.js@3.7.1/dist/chart.min.js"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/lodash.js/4.17.21/lodash.min.js"></script>
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
            
            .tab-container {{
                margin-bottom: 1.5rem;
            }}
            
            .tabs {{
                display: flex;
                border-bottom: 1px solid var(--border-color);
                margin-bottom: 1rem;
            }}
            
            .tab {{
                padding: 0.75rem 1.25rem;
                font-weight: 500;
                cursor: pointer;
                border-bottom: 2px solid transparent;
            }}
            
            .tab.active {{
                color: var(--primary-color);
                border-bottom-color: var(--primary-color);
            }}
            
            .tab-content {{
                display: none;
            }}
            
            .tab-content.active {{
                display: block;
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
            
            .chart-container {{
                height: 300px;
                margin-bottom: 1.5rem;
            }}
            
            .grid-layout {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
                gap: 1.5rem;
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
                <h1>Mobeus Assistant — RAG Analysis Dashboard</h1>
            </div>
            
            <div class="filters card">
                <form method="GET" action="/rag">
                    <div class="form-group">
                        <label for="limit">Max Entries</label>
                        <input type="number" id="limit" name="limit" value="{limit}" min="1" max="1000">
                    </div>
                    
                    <div class="form-group">
                        <label for="filter">Filter Query</label>
                        <input type="text" id="filter" name="filter" value="{filter or ''}" placeholder="Search queries...">
                    </div>
                    
                    <button type="submit">Apply Filters</button>
                </form>
            </div>
            
            <div class="tab-container">
                <div class="tabs">
                    <div class="tab active" data-tab="overview">Overview</div>
                    <div class="tab" data-tab="performance">Performance Analysis</div>
                    <div class="tab" data-tab="sources">Source Analysis</div>
                    <div class="tab" data-tab="queries">Query Analysis</div>
                </div>
                
                <!-- Overview Tab -->
                <div class="tab-content active" id="overview-tab">
                    <div class="card">
                        <div class="card-header">
                            RAG Summary
                        </div>
                        <div class="card-body">
                            <div class="metrics-grid">
                                <div class="metric">
                                    <div class="metric-value">{rag_data["total_entries"]}</div>
                                    <div class="metric-label">Total Queries</div>
                                </div>
                                <div class="metric">
                                    <div class="metric-value">{rag_data["chunks"]["total"]}</div>
                                    <div class="metric-label">Total Chunks Retrieved</div>
                                </div>
                                <div class="metric">
                                    <div class="metric-value">{rag_data["chunks"]["avg"]:.2f}</div>
                                    <div class="metric-label">Avg Chunks Per Query</div>
                                </div>
                                <div class="metric">
                                    <div class="metric-value">{format(rag_data["retrieval_times"]["avg"] * 1000, '.1f')}ms</div>
                                    <div class="metric-label">Avg Retrieval Time</div>
                                </div>
                                <div class="metric">
                                    <div class="metric-value">{len(rag_data["top_sources"])}</div>
                                    <div class="metric-label">Unique Sources</div>
                                </div>
                                <div class="metric">
                                    <div class="metric-value">{rag_data.get("scores", {}).get("avg_score", 0):.3f}</div>
                                    <div class="metric-label">Avg Relevance Score</div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div class="grid-layout">
                        <div class="card">
                            <div class="card-header">
                                Top Documents
                            </div>
                            <div class="card-body">
                                <div class="chart-container">
                                    <canvas id="topSourcesChart"></canvas>
                                </div>
                            </div>
                        </div>
                        
                        <div class="card">
                            <div class="card-header">
                                Retrieval Time Distribution
                            </div>
                            <div class="card-body">
                                <div class="chart-container">
                                    <canvas id="retrievalTimeHistogram"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Performance Analysis Tab -->
                <div class="tab-content" id="performance-tab">
                    <div class="card">
                        <div class="card-header">
                            Query Length vs. Retrieval Time
                        </div>
                        <div class="card-body">
                            <div class="chart-container">
                                <canvas id="queryLengthVsRetrievalTime"></canvas>
                            </div>
                        </div>
                    </div>
                    
                    <div class="grid-layout">
                        <div class="card">
                            <div class="card-header">
                                Retrieval Time Trends
                            </div>
                            <div class="card-body">
                                <div class="chart-container">
                                    <canvas id="retrievalTimeTrends"></canvas>
                                </div>
                            </div>
                        </div>
                        
                        <div class="card">
                            <div class="card-header">
                                Relevance Score Distribution
                            </div>
                            <div class="card-body">
                                <div class="chart-container">
                                    <canvas id="relevanceScoreDistribution"></canvas>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Source Analysis Tab -->
                <div class="tab-content" id="sources-tab">
                    <div class="card">
                        <div class="card-header">
                            Document Retrieval Frequency
                        </div>
                        <div class="card-body">
                            <div class="table-container">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Source</th>
                                            <th>Retrieval Count</th>
                                            <th>Avg Relevance Score</th>
                                        </tr>
                                    </thead>
                                    <tbody id="source-frequency-table">
                                        <!-- Will be populated by JavaScript -->
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            Source Relevance by Query Type
                        </div>
                        <div class="card-body">
                            <div class="chart-container">
                                <canvas id="sourceRelevanceByQueryType"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
                
                <!-- Query Analysis Tab -->
                <div class="tab-content" id="queries-tab">
                    <div class="card">
                        <div class="card-header">
                            Recent Queries
                        </div>
                        <div class="card-body">
                            <div class="table-container">
                                <table>
                                    <thead>
                                        <tr>
                                            <th>Timestamp</th>
                                            <th>Query</th>
                                            <th>Chunks</th>
                                            <th>Retrieval Time</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {"".join([f'''  
                                        <tr>
                                            <td>{entry.get("timestamp", "")}</td>
                                            <td>{entry.get("query", "")}</td>
                                            <td>{len(entry.get("top_chunks", []))}</td>
                                            <td>{entry.get("timings", {}).get("retrieval", 0) * 1000:.1f}ms</td>
                                        </tr>
                                        ''' for entry in entries[:10]])}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    
                    <div class="card">
                        <div class="card-header">
                            Query Classification
                        </div>
                        <div class="card-body">
                            <div class="chart-container">
                                <canvas id="queryClassification"></canvas>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            // Parse RAG data
            const ragData = {rag_data_json};
            
            // Tab switching functionality
            document.querySelectorAll('.tab').forEach(tab => {{
                tab.addEventListener('click', () => {{
                    // Remove active class from all tabs and content
                    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                    
                    // Add active class to clicked tab and corresponding content
                    tab.classList.add('active');
                    document.getElementById(`${{tab.dataset.tab}}-tab`).classList.add('active');
                }});
            }});
            
            // Helper function to format time
            function formatTime(seconds) {{
                return seconds < 0.001 ? 
                    `${{(seconds * 1000000).toFixed(1)}}μs` : 
                    seconds < 1 ? 
                        `${{(seconds * 1000).toFixed(1)}}ms` : 
                        `${{seconds.toFixed(2)}}s`;
            }}
            
            // Helper function to truncate text
            function truncateText(text, maxLength = 20) {{
                return text.length > maxLength ? text.substring(0, maxLength) + '...' : text;
            }}
            
            // Chart 1: Top Sources
            const topSourcesCtx = document.getElementById('topSourcesChart').getContext('2d');
            new Chart(topSourcesCtx, {{
                type: 'bar',
                data: {{
                    labels: ragData.top_sources.map(source => truncateText(source[0])),
                    datasets: [{{
                        label: 'Retrieval Count',
                        data: ragData.top_sources.map(source => source[1]),
                        backgroundColor: '#3b82f6',
                        borderColor: '#2563eb',
                        borderWidth: 1
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: 'y',
                    plugins: {{
                        legend: {{
                            display: false
                        }},
                        tooltip: {{
                            callbacks: {{
                                title: function(context) {{
                                    const index = context[0].dataIndex;
                                    return ragData.top_sources[index][0];
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            title: {{
                                display: true,
                                text: 'Retrieval Count'
                            }}
                        }}
                    }}
                }}
            }});
            
            // Chart 2: Retrieval Time Histogram
            const retrievalTimeData = ragData.query_length_data.map(item => item.retrieval_time);
            const retrievalTimeHistogramCtx = document.getElementById('retrievalTimeHistogram').getContext('2d');
            
            // Create bins for histogram
            const minTime = Math.min(...retrievalTimeData) * 1000; // Convert to ms
            const maxTime = Math.max(...retrievalTimeData) * 1000; // Convert to ms
            const binWidth = (maxTime - minTime) / 10;
            const bins = Array(10).fill(0).map((_, i) => minTime + i * binWidth);
            
            // Count data points in each bin
            const binCounts = Array(10).fill(0);
            retrievalTimeData.forEach(time => {{
                const timeMs = time * 1000;
                const binIndex = Math.min(Math.floor((timeMs - minTime) / binWidth), 9);
                binCounts[binIndex]++;
            }});
            
            new Chart(retrievalTimeHistogramCtx, {{
                type: 'bar',
                data: {{
                    labels: bins.map((bin, i) => `${{bin.toFixed(0)}}-${{(bin + binWidth).toFixed(0)}} ms`),
                    datasets: [{{
                        label: 'Number of Queries',
                        data: binCounts,
                        backgroundColor: '#60a5fa',
                        borderColor: '#3b82f6',
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
                        x: {{
                            title: {{
                                display: true,
                                text: 'Retrieval Time (ms)'
                            }}
                        }},
                        y: {{
                            title: {{
                                display: true,
                                text: 'Number of Queries'
                            }}
                        }}
                    }}
                }}
            }});
            
            // Chart 3: Query Length vs Retrieval Time
            const queryLengthVsRetrievalTimeCtx = document.getElementById('queryLengthVsRetrievalTime').getContext('2d');
            new Chart(queryLengthVsRetrievalTimeCtx, {{
                type: 'scatter',
                data: {{
                    datasets: [{{
                        label: 'Queries',
                        data: ragData.query_length_data.map(item => ({{
                            x: item.query_length,
                            y: item.retrieval_time * 1000, // Convert to ms
                            query: item.query
                        }})),
                        backgroundColor: '#3b82f6',
                        pointRadius: 5,
                        pointHoverRadius: 7
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        tooltip: {{
                            callbacks: {{
                                label: function(context) {{
                                    return `Query: "${{context.raw.query}}"\\nLength: ${{context.raw.x}} chars\\nTime: ${{context.raw.y.toFixed(1)}} ms`;
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        x: {{
                            title: {{
                                display: true,
                                text: 'Query Length (characters)'
                            }}
                        }},
                        y: {{
                            title: {{
                                display: true,
                                text: 'Retrieval Time (ms)'
                            }}
                        }}
                    }}
                }}
            }});
            
            // Chart 4: Retrieval Time Trends
            // (Simplified - would need more data for true trends)
            const retrievalTimeEntries = ragData.query_length_data.slice(0, 20);
            const retrievalTimeTrendsCtx = document.getElementById('retrievalTimeTrends').getContext('2d');
            new Chart(retrievalTimeTrendsCtx, {{
                type: 'line',
                data: {{
                    labels: retrievalTimeEntries.map((_, index) => `Query ${{index + 1}}`),
                    datasets: [{{
                        label: 'Retrieval Time (ms)',
                        data: retrievalTimeEntries.map(item => item.retrieval_time * 1000),
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.4
                    }}]
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {{
                        tooltip: {{
                            callbacks: {{
                                afterLabel: function(context) {{
                                    const index = context.dataIndex;
                                    return `Query: "${{retrievalTimeEntries[index].query}}"`;
                                }}
                            }}
                        }}
                    }},
                    scales: {{
                        y: {{
                            title: {{
                                display: true,
                                text: 'Retrieval Time (ms)'
                            }}
                        }}
                    }}
                }}
            }});
            
            // Chart 5: Relevance Score Distribution
            // Create a histogram of relevance scores if available
            if (ragData.scores && Object.keys(ragData.scores).length > 0) {{
                // This would require relevance scores in the data
                // For now, we'll leave it empty or with a placeholder
                const relevanceScoreDistributionCtx = document.getElementById('relevanceScoreDistribution').getContext('2d');
                new Chart(relevanceScoreDistributionCtx, {{
                    type: 'bar',
                    data: {{
                        labels: ['0.0-0.1', '0.1-0.2', '0.2-0.3', '0.3-0.4', '0.4-0.5', 
                                 '0.5-0.6', '0.6-0.7', '0.7-0.8', '0.8-0.9', '0.9-1.0'],
                        datasets: [{{
                            label: 'Number of Documents',
                            data: [2, 5, 8, 12, 15, 20, 18, 10, 5, 2], // Placeholder data
                            backgroundColor: '#10b981',
                            borderColor: '#059669',
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
                            x: {{
                                title: {{
                                    display: true,
                                    text: 'Relevance Score Range'
                                }}
                            }},
                            y: {{
                                title: {{
                                    display: true,
                                    text: 'Number of Documents'
                                }}
                            }}
                        }}
                    }}
                }});
            }}
            
            // Table: Source Frequency
            const sourceFrequencyTable = document.getElementById('source-frequency-table');
            if (sourceFrequencyTable) {{
                // Process source relevance data to get average scores
                const sourceStats = {{}};
                
                // Aggregate data across query types
                Object.values(ragData.source_relevance_data).forEach(queryTypeSources => {{
                    Object.entries(queryTypeSources).forEach(([source, data]) => {{
                        if (!sourceStats[source]) {{
                            sourceStats[source] = {{
                                count: 0,
                                total_score: 0
                            }};
                        }}
                        
                        sourceStats[source].count += data.count;
                        sourceStats[source].total_score += data.total_score;
                    }});
                }});
                
                // Calculate averages and sort by count
                const sortedSourceStats = Object.entries(sourceStats)
                    .map(([source, stats]) => ({{
                        source,
                        count: stats.count,
                        avg_score: stats.total_score / stats.count
                    }}))
                    .sort((a, b) => b.count - a.count);
                
                // Generate table rows
                sourceFrequencyTable.innerHTML = sortedSourceStats
                    .map(stats => `
                        <tr>
                            <td>${{stats.source}}</td>
                            <td>${{stats.count}}</td>
                            <td>${{stats.avg_score.toFixed(3)}}</td>
                        </tr>
                    `)
                    .join('');
            }}
            
            // Chart 6: Source Relevance by Query Type
            const sourceRelevanceByQueryTypeCtx = document.getElementById('sourceRelevanceByQueryType').getContext('2d');
            
            // Process source relevance data
            const queryTypes = Object.keys(ragData.source_relevance_data);
            const sourceRelevanceDatasets = [];
            
            // Find top 5 sources across all query types
            const allSources = new Set();
            Object.values(ragData.source_relevance_data).forEach(queryTypeSources => {{
                Object.keys(queryTypeSources).forEach(source => allSources.add(source));
            }});
            
            const topSources = Array.from(allSources)
                .map(source => {{
                    let totalCount = 0;
                    Object.values(ragData.source_relevance_data).forEach(queryTypeSources => {{
                        if (queryTypeSources[source]) {{
                            totalCount += queryTypeSources[source].count;
                        }}
                    }});
                    return [source, totalCount];
                }})
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5)
                .map(item => item[0]);
            
            // Create datasets for each source
            topSources.forEach((source, index) => {{
                const data = queryTypes.map(queryType => {{
                    const sourceData = ragData.source_relevance_data[queryType][source];
                    return sourceData ? sourceData.avg_score : 0;
                }});
                
                sourceRelevanceDatasets.push({{
                    label: truncateText(source),
                    data,
                    backgroundColor: [
                        '#3b82f6',
                        '#10b981',
                        '#f59e0b',
                        '#ef4444',
                        '#8b5cf6'
                    ][index],
                    borderColor: [
                        '#2563eb',
                        '#059669',
                        '#d97706',
                        '#dc2626',
                        '#7c3aed'
                    ][index],
                    borderWidth: 1
                }});
            }});
            
            new Chart(sourceRelevanceByQueryTypeCtx, {{
                type: 'radar',
                data: {{
                    labels: queryTypes.map(type => type.replace('_', ' ')),
                    datasets: sourceRelevanceDatasets
                }},
                options: {{
                    responsive: true,
                    maintainAspectRatio: false,
                    scales: {{
                        r: {{
                            min: 0,
                            ticks: {{
                                stepSize: 0.2
                            }}
                        }}
                    }}
                }}
            }});
            
            // Chart 7: Query Classification
            const queryClassificationCtx = document.getElementById('queryClassification').getContext('2d');
            
            // Count queries by type
            const queryTypeCounts = {{}};
            Object.keys(ragData.source_relevance_data || {{}}).forEach(queryType => {{
                queryTypeCounts[queryType] = 0;

                // Count unique queries for this type
                const queries = new Set();
                Object.values(ragData.source_relevance_data[queryType] || {{}}).forEach(sourceData => {{
                    (sourceData.example_queries || []).forEach(query => queries.add(query));
                }});

                queryTypeCounts[queryType] = queries.size;
            }});
            
            new Chart(queryClassificationCtx, {{
                type: 'pie',
                data: {{
                    labels: Object.keys(queryTypeCounts).map(type => type.replace('_', ' ')),
                    datasets: [{{
                        data: Object.values(queryTypeCounts),
                        backgroundColor: [
                            '#3b82f6',
                            '#10b981',
                            '#f59e0b',
                            '#ef4444'
                        ],
                        borderColor: [
                            '#2563eb',
                            '#059669',
                            '#d97706',
                            '#dc2626'
                        ],
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

@router.get("/rag/data")
async def get_rag_data(
    limit: int = Query(100, description="Number of log entries to analyze"),
    filter: Optional[str] = Query(None, description="Filter by query text")
):
    """
    API endpoint to get RAG data as JSON for external use.
    """
    rag_data = get_rag_performance_data(limit=limit, filter_query=filter)
    return JSONResponse(rag_data)
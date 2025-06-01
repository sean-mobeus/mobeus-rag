import os
import json
import datetime
from typing import List, Dict, Any, Optional

from config import DEBUG_LOG_PATH, LOG_DIR
# Tool Strategy definitions (moved from tools_dashboard to avoid circular import)
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

# Paths for JSONL logs
FUNCTION_LOG_PATH = os.path.join(
    LOG_DIR, os.getenv("MOBEUS_FUNCTION_LOG", "function_calls.jsonl")
)
STRATEGY_LOG_PATH = os.path.join(
    LOG_DIR, os.getenv("MOBEUS_STRATEGY_LOG", "strategy_changes.jsonl")
)

def log_strategy_change(user_uuid: str, old_strategy: str, new_strategy: str) -> None:
    """Log strategy changes for analysis."""
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "user_uuid": user_uuid,
        "old_strategy": old_strategy,
        "new_strategy": new_strategy,
        "type": "strategy_change"
    }
    with open(STRATEGY_LOG_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")

def get_function_calls(
    limit: int = 50,
    filter_query: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Extract function call data from logs or debug file."""
    function_calls: List[Dict[str, Any]] = []
    # Try dedicated function call log first
    if os.path.exists(FUNCTION_LOG_PATH):
        try:
            with open(FUNCTION_LOG_PATH, "r") as f:
                lines = f.readlines()
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                # Filter if requested
                if filter_query:
                    fname = entry.get("function_name", "")
                    args = entry.get("arguments", {})
                    if filter_query.lower() not in fname.lower() and \
                       filter_query.lower() not in json.dumps(args).lower():
                        continue
                function_calls.append(entry)
                if len(function_calls) >= limit:
                    return function_calls
        except Exception:
            pass
    # Fallback to debug log
    if os.path.exists(DEBUG_LOG_PATH):
        try:
            with open(DEBUG_LOG_PATH, "r") as f:
                lines = f.readlines()
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                answer = entry.get("answer", "")
                if "function" in answer.lower() or "tool" in answer.lower():
                    fname = None
                    args: Dict[str, Any] = {}
                    # Attempt to extract function name
                    if "calling function:" in answer.lower():
                        part = answer.split("calling function:", 1)[1].strip()
                        fname = part.split()[0].strip("'\"()[]{}").strip()
                    elif "using tool:" in answer.lower():
                        part = answer.split("using tool:", 1)[1].strip()
                        fname = part.split()[0].strip("'\"()[]{}").strip()
                    if fname:
                        if filter_query and filter_query.lower() not in fname.lower():
                            continue
                        function_calls.append({
                            "timestamp": entry.get("timestamp", ""),
                            "query": entry.get("query", ""),
                            "function_name": fname,
                            "arguments": args,
                            "result": None,
                            "execution_time": None,
                            "success": None,
                            "strategy": "unknown"
                        })
                        if len(function_calls) >= limit:
                            return function_calls
        except Exception:
            pass
    # Generate sample data if empty
    if not function_calls:
        function_calls = generate_sample_function_calls(limit)
    return function_calls

def get_strategy_changes(limit: int = 20) -> List[Dict[str, Any]]:
    """Get recent strategy changes for analysis."""
    changes: List[Dict[str, Any]] = []
    if os.path.exists(STRATEGY_LOG_PATH):
        try:
            with open(STRATEGY_LOG_PATH, "r") as f:
                lines = f.readlines()
            for line in reversed(lines):
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                changes.append(entry)
                if len(changes) >= limit:
                    break
        except Exception:
            pass
    return changes

def generate_sample_function_calls(count: int = 10) -> List[Dict[str, Any]]:
    """Generate sample function call data for demonstration."""
    sample_functions = [
        "search_knowledge_base",
        "update_user_memory",
        "get_weather",
        "search_web",
        "calculate",
    ]
    sample_strategies = list(TOOL_STRATEGIES.keys())
    now = datetime.datetime.now()
    samples: List[Dict[str, Any]] = []
    for i in range(count):
        idx = i % len(sample_functions)
        timestamp = (now - datetime.timedelta(minutes=i * 5)).isoformat()
        success = (i % 10) != 0
        samples.append({
            "timestamp": timestamp,
            "query": f"Sample query {i+1}",
            "function_name": sample_functions[idx],
            "arguments": {"query": f"Sample query {i+1}"},
            "result": {"answer": "Sample result"} if success else {"error": "Function execution failed"},
            "execution_time": (i % 5) * 0.1 + 0.1,
            "success": success,
            "strategy": sample_strategies[i % len(sample_strategies)],
        })
    return samples

def analyze_function_calls(
    function_calls: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Analyze function call data for dashboard insights."""
    if not function_calls:
        return {
            "total_calls": 0,
            "success_rate": 0,
            "function_frequency": {},
            "avg_execution_time": 0,
            "execution_times": {},
            "strategy_effectiveness": {},
        }
    total = len(function_calls)
    success_count = sum(1 for c in function_calls if c.get("success"))
    success_rate = (success_count / total) * 100 if total else 0
    freq: Dict[str, int] = {}
    times: Dict[str, List[float]] = {}
    strat_stats: Dict[str, Dict[str, int]] = {}
    for call in function_calls:
        fname = call.get("function_name", "unknown")
        strat = call.get("strategy", "unknown")
        freq[fname] = freq.get(fname, 0) + 1
        et = call.get("execution_time")
        if isinstance(et, (int, float)):
            times.setdefault(fname, []).append(et)
        ss = strat_stats.setdefault(strat, {"total": 0, "success": 0})
        ss["total"] += 1
        if call.get("success"):
            ss["success"] += 1
    avg_times: Dict[str, float] = {f: sum(t) / len(t) for f, t in times.items() if t}
    all_times = [val for sub in times.values() for val in sub]
    avg_all = sum(all_times) / len(all_times) if all_times else 0
    strat_eff: Dict[str, Dict[str, float]] = {
        strat: {"success_rate": (data["success"] / data["total"]) * 100, "total_calls": data["total"]}
        for strat, data in strat_stats.items() if data.get("total")
    }
    return {
        "total_calls": total,
        "success_rate": success_rate,
        "function_frequency": freq,
        "avg_execution_time": avg_all,
        "execution_times": avg_times,
        "strategy_effectiveness": strat_eff,
    }
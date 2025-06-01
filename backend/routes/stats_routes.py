from fastapi import APIRouter, Query, HTTPException
from typing import Optional

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"service": "stats", "status": "healthy"}

@router.get("/function_calls")
async def get_function_calls(limit: int = Query(50, description="Max number of function calls"),
                             filter: Optional[str] = Query(None, description="Filter by function name")):
    """Retrieve recent function call entries."""
    from stats.collector import get_function_calls as _get_calls
    return _get_calls(limit=limit, filter_query=filter)

@router.get("/strategy_changes")
async def get_strategy_changes(limit: int = Query(20, description="Max number of strategy changes")):
    """Retrieve recent strategy change entries."""
    from stats.collector import get_strategy_changes
    return get_strategy_changes(limit=limit)

@router.get("/analysis")
async def get_function_analysis(limit: int = Query(50, description="Max number of function calls"),
                               filter: Optional[str] = Query(None, description="Filter by function name")):
    """Return aggregated function call analytics."""
    from stats.collector import get_function_calls, analyze_function_calls
    calls = get_function_calls(limit=limit, filter_query=filter)
    return analyze_function_calls(calls)

@router.get("/data")
async def get_stats_data(limit: int = Query(50, description="Max number of function calls"),
                         filter: Optional[str] = Query(None, description="Filter by function name")):
    """Return combined function calls, strategy changes, and analytics."""
    from stats.collector import get_function_calls, get_strategy_changes, analyze_function_calls
    from stats.tools_dashboard import TOOL_STRATEGIES
    calls = get_function_calls(limit=limit, filter_query=filter)
    changes = get_strategy_changes(limit=20)
    analysis = analyze_function_calls(calls)
    return {
        "function_calls": calls,
        "strategy_changes": changes,
        "analysis": analysis,
        "strategies": TOOL_STRATEGIES,
    }
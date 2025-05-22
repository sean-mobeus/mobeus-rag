# dashboard_integration.py
"""
This module integrates the admin dashboard with the main Mobeus backend.
Includes fallback options in case modules can't be imported.
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
import importlib
import sys

def setup_admin_dashboard(app: FastAPI, prefix: str = "/admin"):
    """
    Set up all admin dashboard routes with proper prefix
    to avoid conflicts with existing routes.
    
    Args:
        app: The FastAPI application instance
        prefix: URL prefix for all dashboard routes (default: "/admin")
    """
    # Import routers with fallbacks for missing dependencies
    routers_to_include = []
    
    # Try to import main dashboard
    try:
        from stats.main_dashboard import router as main_dashboard_router
        routers_to_include.append(("Main Dashboard", main_dashboard_router))
    except ImportError as e:
        print(f"Warning: Could not import main dashboard: {e}")
        # Try the simple dashboard as fallback
        try:
            from stats.simple_dashboard import router as simple_dashboard_router
            routers_to_include.append(("Simple Dashboard", simple_dashboard_router))
        except ImportError as e2:
            print(f"Warning: Could not import simple dashboard: {e2}")
    
    # Try to import other dashboard components
    dashboard_modules = [
        ("Config Dashboard", "stats.config_dashboard"),
        ("Debug Dashboard", "stats.debug_dashboard"),
        ("RAG Dashboard", "stats.rag_dashboard"),
        ("Tools Dashboard", "stats.tools_dashboard"),
        ("Session Dashboard", "stats.session_dashboard")
    ]
    
    for name, module_path in dashboard_modules:
        try:
            module = importlib.import_module(module_path)
            if hasattr(module, 'router'):
                routers_to_include.append((name, module.router))
            else:
                print(f"Warning: {name} module does not have a 'router' attribute")
        except ImportError as e:
            print(f"Warning: Could not import {name}: {e}")
    
    # Mount all dashboard routers with the admin prefix
    for name, router in routers_to_include:
        app.include_router(router, prefix=prefix)
        print(f"✅ {name} mounted at {prefix}")
    
    if not routers_to_include:
        print("❌ No dashboard components could be loaded")
        
        # Create a simple fallback route
        @app.get(f"{prefix}/", include_in_schema=False)
        async def admin_fallback():
            return HTMLResponse(content="""
            <html>
                <head><title>Mobeus Admin</title></head>
                <body>
                    <h1>Mobeus Admin Dashboard</h1>
                    <p>Dashboard components could not be loaded. Check logs for details.</p>
                </body>
            </html>
            """)
    
    # Add redirection from admin root to main dashboard
    @app.get(prefix, include_in_schema=False)
    async def redirect_to_admin():
        return RedirectResponse(url=f"{prefix}/")
    
    return app
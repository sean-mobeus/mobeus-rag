# main_dashboard.py
import os
import datetime
import platform
import psutil
from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import List, Dict, Any, Optional
import sys
import pkg_resources

router = APIRouter()

def get_system_info():
    """Get system information for the dashboard."""
    try:
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(psutil.boot_time())
        uptime_str = f"{uptime.days} days, {uptime.seconds // 3600} hours, {(uptime.seconds // 60) % 60} minutes"
        
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Get Python packages
        installed_packages = sorted([
            (p.key, p.version) for p in pkg_resources.working_set
        ], key=lambda x: x[0].lower())
        
        key_packages = [p for p in installed_packages if p[0] in [
            'fastapi', 'openai', 'chromadb', 'uvicorn', 'psycopg2', 'psycopg2-binary',
            'pydantic', 'python-dotenv', 'websockets', 'requests'
        ]]
        
        return {
            "system": {
                "os": platform.platform(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
                "uptime": uptime_str
            },
            "resources": {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_total": memory.total,
                "memory_available": memory.available,
                "memory_percent": memory.percent,
                "disk_total": disk.total,
                "disk_free": disk.free,
                "disk_percent": disk.percent
            },
            "packages": key_packages
        }
    except Exception as e:
        print(f"Error getting system info: {e}")
        return {
            "system": {
                "error": str(e)
            },
            "resources": {},
            "packages": []
        }

@router.get("/", response_class=HTMLResponse)
async def main_dashboard(request: Request):
    """
    Main dashboard that integrates all individual dashboards.
    """
    system_info = get_system_info()
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Mobeus Assistant — Admin Dashboard</title>
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
                --sidebar-width: 240px;
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
                display: flex;
                min-height: 100vh;
            }}
            
            .sidebar {{
                width: var(--sidebar-width);
                background-color: #1f2937;
                color: white;
                position: fixed;
                top: 0;
                left: 0;
                bottom: 0;
                overflow-y: auto;
                z-index: 10;
            }}
            
            .sidebar-header {{
                padding: 1.5rem;
                border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            }}
            
            .logo {{
                font-size: 1.25rem;
                font-weight: 600;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }}
            
            .logo-icon {{
                width: 24px;
                height: 24px;
                background-color: var(--primary-color);
                border-radius: 4px;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            
            .sidebar-content {{
                padding: 1rem 0;
            }}
            
            .sidebar-section {{
                margin-bottom: 1rem;
            }}
            
            .sidebar-section-title {{
                padding: 0.5rem 1.5rem;
                font-size: 0.75rem;
                text-transform: uppercase;
                letter-spacing: 0.05em;
                color: rgba(255, 255, 255, 0.6);
            }}
            
            .sidebar-menu {{
                list-style: none;
            }}
            
            .sidebar-menu-item {{
                display: block;
                padding: 0.75rem 1.5rem;
                color: rgba(255, 255, 255, 0.8);
                text-decoration: none;
                transition: background-color 0.2s;
                display: flex;
                align-items: center;
                gap: 0.75rem;
            }}
            
            .sidebar-menu-item:hover {{
                background-color: rgba(255, 255, 255, 0.1);
            }}
            
            .sidebar-menu-item.active {{
                background-color: var(--primary-color);
                color: white;
            }}
            
            .sidebar-footer {{
                padding: 1rem 1.5rem;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
                font-size: 0.75rem;
                color: rgba(255, 255, 255, 0.6);
            }}
            
            .main-content {{
                flex: 1;
                margin-left: var(--sidebar-width);
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
            
            .dashboard-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
                gap: 1.5rem;
                margin-bottom: 1.5rem;
            }}
            
            .metric {{
                background-color: var(--card-color);
                border-radius: 0.5rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                padding: 1.5rem;
                display: flex;
                flex-direction: column;
            }}
            
            .metric-header {{
                font-size: 0.875rem;
                color: #6b7280;
                margin-bottom: 0.5rem;
                display: flex;
                align-items: center;
                gap: 0.5rem;
            }}
            
            .metric-value {{
                font-size: 1.5rem;
                font-weight: 600;
                margin-bottom: 0.25rem;
            }}
            
            .metric-description {{
                font-size: 0.875rem;
                color: #6b7280;
            }}
            
            .progress-bar {{
                height: 4px;
                background-color: #e5e7eb;
                border-radius: 2px;
                overflow: hidden;
                margin-top: 0.75rem;
            }}
            
            .progress-bar-fill {{
                height: 100%;
                transition: width 0.3s ease;
            }}
            
            .progress-bar-fill.good {{
                background-color: var(--good-color);
            }}
            
            .progress-bar-fill.warning {{
                background-color: var(--warning-color);
            }}
            
            .progress-bar-fill.bad {{
                background-color: var(--bad-color);
            }}
            
            .grid-2 {{
                display: grid;
                grid-template-columns: 2fr 1fr;
                gap: 1.5rem;
            }}
            
            .system-info {{
                display: grid;
                grid-template-columns: auto 1fr;
                gap: 0.75rem 1.5rem;
            }}
            
            .system-info-label {{
                font-weight: 500;
                color: #6b7280;
            }}
            
            .package-list {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
                gap: 0.5rem;
            }}
            
            .package {{
                font-size: 0.875rem;
                background-color: #f3f4f6;
                padding: 0.5rem 0.75rem;
                border-radius: 0.375rem;
                display: flex;
                justify-content: space-between;
            }}
            
            .package-name {{
                font-weight: 500;
            }}
            
            .package-version {{
                color: #6b7280;
            }}
            
            .dashboard-link {{
                display: block;
                text-decoration: none;
                color: inherit;
            }}
            
            .dashboard-card {{
                background-color: var(--card-color);
                border-radius: 0.5rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
                padding: 1.5rem;
                display: flex;
                flex-direction: column;
                height: 100%;
                transition: transform 0.2s, box-shadow 0.2s;
            }}
            
            .dashboard-card:hover {{
                transform: translateY(-4px);
                box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
            }}
            
            .dashboard-card-icon {{
                width: 48px;
                height: 48px;
                background-color: var(--primary-light);
                color: var(--primary-color);
                border-radius: 0.5rem;
                display: flex;
                align-items: center;
                justify-content: center;
                margin-bottom: 1rem;
            }}
            
            .dashboard-card-title {{
                font-size: 1.125rem;
                font-weight: 600;
                margin-bottom: 0.5rem;
            }}
            
            .dashboard-card-description {{
                font-size: 0.875rem;
                color: #6b7280;
                flex-grow: 1;
            }}
            
            .dashboard-card-cta {{
                margin-top: 1rem;
                font-size: 0.875rem;
                color: var(--primary-color);
                font-weight: 500;
                display: flex;
                align-items: center;
                gap: 0.25rem;
            }}
            
            @media (max-width: 768px) {{
                .sidebar {{
                    width: 100%;
                    position: relative;
                    display: none;
                }}
                
                .main-content {{
                    margin-left: 0;
                }}
                
                .grid-2 {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="logo">
                    <div class="logo-icon">M</div>
                    <span>Mobeus Admin</span>
                </div>
            </div>
            
            <div class="sidebar-content">
                <div class="sidebar-section">
                    <div class="sidebar-section-title">Dashboards</div>
                    <nav class="sidebar-menu">
                        <a href="/" class="sidebar-menu-item active">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="3" y="3" width="7" height="7"></rect>
                                <rect x="14" y="3" width="7" height="7"></rect>
                                <rect x="14" y="14" width="7" height="7"></rect>
                                <rect x="3" y="14" width="7" height="7"></rect>
                            </svg>
                            Overview
                        </a>
                        <a href="/config" class="sidebar-menu-item">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="3"></circle>
                                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                            </svg>
                            Configuration
                        </a>
                        <a href="/debug" class="sidebar-menu-item">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
                            </svg>
                            Debug Logs
                        </a>
                        <a href="/rag" class="sidebar-menu-item">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                                <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                                <line x1="12" y1="22.08" x2="12" y2="12"></line>
                            </svg>
                            RAG Analysis
                        </a>
                        <a href="/tools" class="sidebar-menu-item">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="4" y1="21" x2="4" y2="14"></line>
                                <line x1="4" y1="10" x2="4" y2="3"></line>
                                <line x1="12" y1="21" x2="12" y2="12"></line>
                                <line x1="12" y1="8" x2="12" y2="3"></line>
                                <line x1="20" y1="21" x2="20" y2="16"></line>
                                <line x1="20" y1="12" x2="20" y2="3"></line>
                                <line x1="1" y1="14" x2="7" y2="14"></line>
                                <line x1="9" y1="8" x2="15" y2="8"></line>
                                <line x1="17" y1="16" x2="23" y2="16"></line>
                            </svg>
                            Tool Calls
                        </a>
                        <a href="/sessions" class="sidebar-menu-item">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                                <circle cx="9" cy="7" r="4"></circle>
                                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                            </svg>
                            Sessions
                        </a>
                    </nav>
                </div>
                
                <div class="sidebar-section">
                    <div class="sidebar-section-title">Environment</div>
                    <nav class="sidebar-menu">
                        <a href="#system-info" class="sidebar-menu-item">
                            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect>
                                <line x1="8" y1="21" x2="16" y2="21"></line>
                                <line x1="12" y1="17" x2="12" y2="21"></line>
                            </svg>
                            System Info
                        </a>
                    </nav>
                </div>
            </div>
            
            <div class="sidebar-footer">
                Mobeus Assistant v1.0.0
            </div>
        </div>
        
        <div class="main-content">
            <div class="header">
                <h1>Mobeus Assistant Admin Dashboard</h1>
            </div>
            
            <div class="dashboard-grid">
                <div class="metric">
                    <div class="metric-header">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                        </svg>
                        CPU Usage
                    </div>
                    <div class="metric-value">{system_info["resources"].get("cpu_percent", 0)}%</div>
                    <div class="progress-bar">
                        <div 
                            class="progress-bar-fill {
                                'good' if system_info['resources'].get('cpu_percent', 0) < 50 else
                                'warning' if system_info['resources'].get('cpu_percent', 0) < 80 else
                                'bad'
                            }"
                            style="width: {system_info['resources'].get('cpu_percent', 0)}%;"
                        ></div>
                    </div>
                </div>
                
                <div class="metric">
                    <div class="metric-header">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <rect x="1" y="4" width="22" height="16" rx="2" ry="2"></rect>
                            <line x1="1" y1="10" x2="23" y2="10"></line>
                        </svg>
                        Memory Usage
                    </div>
                    <div class="metric-value">{system_info["resources"].get("memory_percent", 0)}%</div>
                    <div class="metric-description">
                        {system_info["resources"].get("memory_available", 0) / (1024 * 1024 * 1024):.1f} GB available
                    </div>
                    <div class="progress-bar">
                        <div 
                            class="progress-bar-fill {
                                'good' if system_info['resources'].get('memory_percent', 0) < 60 else
                                'warning' if system_info['resources'].get('memory_percent', 0) < 85 else
                                'bad'
                            }"
                            style="width: {system_info['resources'].get('memory_percent', 0)}%;"
                        ></div>
                    </div>
                </div>
                
                <div class="metric">
                    <div class="metric-header">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"></circle>
                            <polyline points="12 6 12 12 16 14"></polyline>
                        </svg>
                        System Uptime
                    </div>
                    <div class="metric-value">{system_info["system"].get("uptime", "Unknown").split(',')[0]}</div>
                    <div class="metric-description">
                        {', '.join(system_info["system"].get("uptime", "").split(',')[1:])}
                    </div>
                </div>
                
                <div class="metric">
                    <div class="metric-header">
                        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#6b7280" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                            <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                            <line x1="12" y1="22.08" x2="12" y2="12"></line>
                        </svg>
                        Disk Usage
                    </div>
                    <div class="metric-value">{system_info["resources"].get("disk_percent", 0)}%</div>
                    <div class="metric-description">
                        {system_info["resources"].get("disk_free", 0) / (1024 * 1024 * 1024):.1f} GB free
                    </div>
                    <div class="progress-bar">
                        <div 
                            class="progress-bar-fill {
                                'good' if system_info['resources'].get('disk_percent', 0) < 70 else
                                'warning' if system_info['resources'].get('disk_percent', 0) < 90 else
                                'bad'
                            }"
                            style="width: {system_info['resources'].get('disk_percent', 0)}%;"
                        ></div>
                    </div>
                </div>
            </div>
            
            <h2>Admin Dashboards</h2>
            
            <div class="dashboard-grid">
                <a href="/config" class="dashboard-link">
                    <div class="dashboard-card">
                        <div class="dashboard-card-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="3"></circle>
                                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                            </svg>
                        </div>
                        <div class="dashboard-card-title">Configuration</div>
                        <div class="dashboard-card-description">
                            Configure OpenAI API settings, model parameters, RAG settings and more.
                        </div>
                        <div class="dashboard-card-cta">
                            Open Configuration
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="9 18 15 12 9 6"></polyline>
                            </svg>
                        </div>
                    </div>
                </a>
                
                <a href="/debug" class="dashboard-link">
                    <div class="dashboard-card">
                        <div class="dashboard-card-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path>
                            </svg>
                        </div>
                        <div class="dashboard-card-title">Debug Logs</div>
                        <div class="dashboard-card-description">
                            View detailed logs, query/response pairs, and performance metrics.
                        </div>
                        <div class="dashboard-card-cta">
                            View Logs
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="9 18 15 12 9 6"></polyline>
                            </svg>
                        </div>
                    </div>
                </a>
                
                <a href="/rag" class="dashboard-link">
                    <div class="dashboard-card">
                        <div class="dashboard-card-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path>
                                <polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline>
                                <line x1="12" y1="22.08" x2="12" y2="12"></line>
                            </svg>
                        </div>
                        <div class="dashboard-card-title">RAG Analysis</div>
                        <div class="dashboard-card-description">
                            Analyze retrieval performance, relevance scores, and document usage patterns.
                        </div>
                        <div class="dashboard-card-cta">
                            View RAG Analytics
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="9 18 15 12 9 6"></polyline>
                            </svg>
                        </div>
                    </div>
                </a>
                
                <a href="/tools" class="dashboard-link">
                    <div class="dashboard-card">
                        <div class="dashboard-card-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <line x1="4" y1="21" x2="4" y2="14"></line>
                                <line x1="4" y1="10" x2="4" y2="3"></line>
                                <line x1="12" y1="21" x2="12" y2="12"></line>
                                <line x1="12" y1="8" x2="12" y2="3"></line>
                                <line x1="20" y1="21" x2="20" y2="16"></line>
                                <line x1="20" y1="12" x2="20" y2="3"></line>
                                <line x1="1" y1="14" x2="7" y2="14"></line>
                                <line x1="9" y1="8" x2="15" y2="8"></line>
                                <line x1="17" y1="16" x2="23" y2="16"></line>
                            </svg>
                        </div>
                        <div class="dashboard-card-title">Tool Calls</div>
                        <div class="dashboard-card-description">
                            Monitor function calls, success rates, and execution times for tools and plugins.
                        </div>
                        <div class="dashboard-card-cta">
                            View Tool Analytics
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="9 18 15 12 9 6"></polyline>
                            </svg>
                        </div>
                    </div>
                </a>
                
                <a href="/sessions" class="dashboard-link">
                    <div class="dashboard-card">
                        <div class="dashboard-card-icon">
                            <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path>
                                <circle cx="9" cy="7" r="4"></circle>
                                <path d="M23 21v-2a4 4 0 0 0-3-3.87"></path>
                                <path d="M16 3.13a4 4 0 0 1 0 7.75"></path>
                            </svg>
                        </div>
                        <div class="dashboard-card-title">Sessions</div>
                        <div class="dashboard-card-description">
                            View and manage user sessions, conversation history, and user activity.
                        </div>
                        <div class="dashboard-card-cta">
                            Manage Sessions
                            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <polyline points="9 18 15 12 9 6"></polyline>
                            </svg>
                        </div>
                    </div>
                </a>
            </div>
            
            <div class="grid-2">
                <div class="card" id="system-info">
                    <div class="card-header">
                        System Information
                    </div>
                    <div class="card-body">
                        <div class="system-info">
                            <div class="system-info-label">Operating System</div>
                            <div>{system_info["system"].get("os", "Unknown")}</div>
                            
                            <div class="system-info-label">Processor</div>
                            <div>{system_info["system"].get("processor", "Unknown")}</div>
                            
                            <div class="system-info-label">Python Version</div>
                            <div>{system_info["system"].get("python_version", "Unknown")}</div>
                            
                            <div class="system-info-label">Memory</div>
                            <div>{system_info["resources"].get("memory_total", 0) / (1024 * 1024 * 1024):.1f} GB Total</div>
                            
                            <div class="system-info-label">Disk</div>
                            <div>{system_info["resources"].get("disk_total", 0) / (1024 * 1024 * 1024):.1f} GB Total</div>
                            
                            <div class="system-info-label">Uptime</div>
                            <div>{system_info["system"].get("uptime", "Unknown")}</div>
                        </div>
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">
                        Key Packages
                    </div>
                    <div class="card-body">
                        <div class="package-list">
                            {"".join([
                                f'''
                            <div class="package">
                                <span class="package-name">{pkg[0]}</span>
                                <span class="package-version">{pkg[1]}</span>
                            </div>
                            ''' for pkg in system_info["packages"]
                            ])}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)
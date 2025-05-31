# stats/config_dashboard.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from typing import Optional
import os
import json
from pathlib import Path
from config import runtime_config
# Import default summary prompt for session memory
from memory.session_memory import get_summary_prompt
from config.openaiconfig import (
    REALTIME_VOICES,
    REALTIME_MODELS,
    REALTIME_AUDIO_FORMATS,
    DEFAULT_REALTIME_CONFIG
)

router = APIRouter()

# Configuration sections and their parameters
CONFIG_SECTIONS = {
    "Core Settings": {
        "SESSION_MEMORY_CHAR_LIMIT": {
            "label": "Session Memory Limit (chars)",
            "type": "number",
            "help": "Character limit for session memory before auto-summarization",
            "min": 5000,
            "max": 20000
        },
        "SESSION_SUMMARY_PROMPT": {
            "label": "Conversation Summary Prompt", 
            "type": "textarea",
            "help": "Prompt used to summarize conversations for persistent memory"
        },
        "TONE_STYLE": {
            "label": "Assistant Tone Style",
            "type": "select",
            "options": ["empathetic", "casual", "professional", "friendly", "concise"],
            "help": "Personality style for assistant responses"
        }
    },
    "System Instructions": {
        "SYSTEM_PROMPT": {
            "label": "System Prompt",
            "type": "textarea",
            "help": "Main system instructions that define the assistant's behavior and capabilities. Use {tone_style} placeholder for dynamic tone insertion."
        }
    },
    "Model Settings": {
        "GPT_MODEL": {
            "label": "GPT Model",
            "type": "select",
            "options": ["gpt-4", "gpt-4o", "gpt-3.5-turbo"],
            "help": "Model used for standard text completions (non-realtime)"
        },
        "REALTIME_MODEL": {
            "label": "Realtime Model",
            "type": "select",
            "options": REALTIME_MODELS,
            "help": "Model used for realtime voice conversations"
        },
        "TEMPERATURE": {
            "label": "Temperature",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.1,
            "help": "Controls randomness of output (0=deterministic, 1=creative)"
        }
    },
    "Realtime Voice Settings": {
        "REALTIME_VOICE": {
            "label": "Voice",
            "type": "select",
            "options": REALTIME_VOICES,
            "help": "Voice used for text-to-speech in realtime conversations"
        },
        "REALTIME_AUDIO_FORMAT": {
            "label": "Audio Format",
            "type": "select",
            "options": REALTIME_AUDIO_FORMATS,
            "help": "Audio format for realtime conversations"
        },
        "REALTIME_MODALITIES": {
            "label": "Response Modalities",
            "type": "multiselect",
            "options": ["text", "audio"],
            "help": "Response types to enable (text, audio, or both)"
        }
    },
    "RAG Settings": {
        "RAG_RESULT_COUNT": {
            "label": "Number of Results",
            "type": "number",
            "help": "Number of documents to retrieve for each query",
            "min": 1,
            "max": 10
        },
        "EMBED_MODEL": {
            "label": "Embedding Model",
            "type": "select",
            "options": ["text-embedding-ada-002", "text-embedding-3-small", "text-embedding-3-large"],
            "help": "Model used for document embeddings"
        },
        "RAG_TEMPERATURE": {
            "label": "RAG Temperature",
            "type": "range",
            "min": 0,
            "max": 1,
            "step": 0.1,
            "help": "Temperature for RAG completions"
        }
    },
    "Turn Detection": {
        "TURN_DETECTION_TYPE": {
            "label": "Turn Detection Type",
            "type": "select",
            "options": ["server_vad", "client_vad"],
            "help": "Method used to detect when user has finished speaking"
        },
        "TURN_DETECTION_THRESHOLD": {
            "label": "VAD Threshold",
            "type": "range",
            "min": 0.1,
            "max": 0.9,
            "step": 0.1,
            "help": "Threshold for voice activity detection (higher = less sensitive)"
        },
        "TURN_DETECTION_SILENCE_MS": {
            "label": "Silence Duration (ms)",
            "type": "number",
            "min": 100,
            "max": 1000,
            "help": "How many milliseconds of silence before turn ends"
        }
    }
}

@router.get("/config", response_class=HTMLResponse)
async def config_dashboard(request: Request):
    """
    Render the enhanced configuration dashboard with all parameters
    organized into sections.
    """
    # Get current configuration values
    current_config = runtime_config.all_config()

    # DEBUG CODE TEMPORARILY:
    print("🔍 DEBUG: Current config values:")
    for key, value in current_config.items():
        print(f"  {key}: {repr(value)}")
    print("🔍 DEBUG: Default config values:")
    for key, value in runtime_config.DEFAULT_CONFIG.items():
        print(f"  {key}: {repr(value)}")
    # END DEBUG CODE

    # Ensure the conversation summary prompt shows the default or saved value
    current_config["SESSION_SUMMARY_PROMPT"] = current_config.get("SESSION_SUMMARY_PROMPT") or get_summary_prompt()
    current_config["SYSTEM_PROMPT"] = current_config.get("SYSTEM_PROMPT") or runtime_config.DEFAULT_CONFIG["SYSTEM_PROMPT"]

    
    # Show success/reset messages if present
    query_params = dict(request.query_params)
    success_message = ""
    if query_params.get("saved") == "true":
        success_message = '<div class="success-message">✅ Configuration saved successfully!</div>'
    elif query_params.get("reset") == "true":
        success_message = '<div class="success-message">✅ Configuration reset to defaults!</div>'
    
    # Create HTML for the configuration sections
    sections_html = []
    
    for section_name, params in CONFIG_SECTIONS.items():
        section_html = f"""
        <div class="config-section">
            <h3>{section_name}</h3>
            <div class="section-content">
        """
        
        for key, param in params.items():
            value = current_config.get(key, "")
            label = param.get("label", key)
            param_type = param.get("type", "text")
            help_text = param.get("help", "")
            
            input_html = ""
            if param_type == "select":
                options = param.get("options", [])
                options_html = "".join([
                    f'<option value="{opt}" {"selected" if str(opt) == str(value) else ""}>{opt}</option>'
                    for opt in options
                ])
                input_html = f'<select name="{key}" class="form-control">{options_html}</select>'
            
            elif param_type == "multiselect":
                options = param.get("options", [])
                current_values = value if isinstance(value, list) else [value] if value else []
                checkboxes_html = "".join([
                    f"""
                    <div class="form-check">
                        <input type="checkbox" name="{key}" value="{opt}" 
                               class="form-check-input" id="{key}_{opt}"
                               {"checked" if opt in current_values else ""}>
                        <label class="form-check-label" for="{key}_{opt}">{opt}</label>
                    </div>
                    """
                    for opt in options
                ])
                input_html = f'<div class="checkbox-group">{checkboxes_html}</div>'
            
            elif param_type == "range":
                min_val = param.get("min", 0)
                max_val = param.get("max", 1)
                step = param.get("step", 0.1)
                input_html = f"""
                <div class="range-container">
                    <input type="range" name="{key}" min="{min_val}" max="{max_val}" 
                           step="{step}" value="{value}" class="form-range">
                    <span class="range-value">{value}</span>
                </div>
                """
            
            elif param_type == "number":
                min_val = param.get("min", "")
                max_val = param.get("max", "")
                min_attr = f'min="{min_val}"' if min_val != "" else ""
                max_attr = f'max="{max_val}"' if max_val != "" else ""
                input_html = f'<input type="number" name="{key}" value="{value}" {min_attr} {max_attr} class="form-control">'
            
            elif param_type == "textarea":
                # For textarea, we need to handle multi-line content properly
                current_value = str(value).replace('"', '&quot;').replace("'", "&#39;")
                input_html = f'<textarea name="{key}" rows="6" class="form-control" placeholder="{help_text}">{current_value}</textarea>'
            
            else:  # Default to text input
                input_html = f'<input type="text" name="{key}" value="{value}" class="form-control">'
            
            section_html += f"""
            <div class="form-group">
                <label for="{key}" class="form-label">
                    {label}
                    <span class="help-tooltip" title="{help_text}">?</span>
                </label>
                {input_html}
            </div>
            """
        
        section_html += """
            </div>
        </div>
        """
        
        sections_html.append(section_html)
    
    # Create the complete HTML document
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Mobeus Assistant — Config Dashboard</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            :root {{
                --primary-color: #2563eb;
                --secondary-color: #1e40af;
                --background-color: #f9fafb;
                --card-color: #ffffff;
                --text-color: #1f2937;
                --border-color: #e5e7eb;
            }}
            
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                background-color: var(--background-color);
                color: var(--text-color);
                line-height: 1.5;
                padding: 2rem;
                margin: 0;
            }}
            
            h1, h2, h3 {{
                color: var(--text-color);
                margin-top: 0;
            }}
            
            h1 {{
                font-size: 1.8rem;
                margin-bottom: 1.5rem;
            }}
            
            h3 {{
                font-size: 1.2rem;
                padding-bottom: 0.5rem;
                border-bottom: 1px solid var(--border-color);
                margin-bottom: 1rem;
            }}
            
            .dashboard-container {{
                max-width: 1200px;
                margin: 0 auto;
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
            
            .config-form {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(500px, 1fr));
                gap: 1.5rem;
                margin-bottom: 1.5rem;
            }}
            
            .config-section {{
                background-color: var(--card-color);
                border-radius: 0.5rem;
                padding: 1.5rem;
                box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
            }}
            
            .section-content {{
                display: grid;
                gap: 1rem;
            }}
            
            .form-group {{
                display: flex;
                flex-direction: column;
                gap: 0.5rem;
            }}
            
            .form-label {{
                font-weight: 500;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            
            .form-control {{
                padding: 0.5rem;
                border: 1px solid var(--border-color);
                border-radius: 0.25rem;
                font-size: 1rem;
                width: 100%;
                font-family: inherit;
            }}
            
            textarea.form-control {{
                resize: vertical;
                min-height: 100px;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
                font-size: 0.875rem;
            }}

            textarea[name="SYSTEM_PROMPT"] {{
                min-height: 200px;
                font-size: 0.875rem;
            }}
            
            .form-range {{
                width: 100%;
            }}
            
            .range-container {{
                display: flex;
                align-items: center;
                gap: 1rem;
            }}
            
            .range-value {{
                min-width: 2.5rem;
                text-align: center;
                font-weight: 500;
            }}
            
            .checkbox-group {{
                display: flex;
                flex-wrap: wrap;
                gap: 0.5rem;
            }}
            
            .form-check {{
                display: flex;
                align-items: center;
                gap: 0.25rem;
            }}
            
            .help-tooltip {{
                display: inline-flex;
                justify-content: center;
                align-items: center;
                width: 1rem;
                height: 1rem;
                border-radius: 50%;
                background-color: #e5e7eb;
                color: #6b7280;
                font-size: 0.75rem;
                cursor: help;
                position: relative;
            }}
            
            .help-tooltip:hover::after {{
                content: attr(title);
                position: absolute;
                z-index: 1;
                bottom: 125%;
                left: 50%;
                transform: translateX(-50%);
                min-width: 200px;
                padding: 0.5rem;
                background-color: #374151;
                color: white;
                border-radius: 0.25rem;
                font-size: 0.75rem;
                font-weight: normal;
                text-align: center;
                white-space: normal;
            }}
            
            .button-group {{
                display: flex;
                justify-content: flex-end;
                gap: 1rem;
                margin-top: 1rem;
            }}
            
            .btn {{
                padding: 0.75rem 1.5rem;
                border-radius: 0.375rem;
                font-weight: 500;
                cursor: pointer;
                border: none;
                font-size: 1rem;
                transition: all 0.2s;
            }}
            
            .btn-primary {{
                background-color: var(--primary-color);
                color: white;
            }}
            
            .btn-secondary {{
                background-color: #e5e7eb;
                color: #1f2937;
            }}
            
            .btn:hover {{
                opacity: 0.9;
                transform: translateY(-1px);
            }}
            
            .success-message {{
                background-color: #d1fae5;
                border: 1px solid #10b981;
                color: #065f46;
                padding: 1rem;
                border-radius: 0.375rem;
                margin-bottom: 1rem;
            }}
            
            @media (max-width: 768px) {{
                .config-form {{
                    grid-template-columns: 1fr;
                }}
                
                body {{
                    padding: 1rem;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="dashboard-container">
            <div class="breadcrumb">
                <a href="/admin/">Dashboard</a>
                <span>/</span>
                <span>Configuration</span>
            </div>
            
            <h1>🎛️ Mobeus Assistant — Configuration Dashboard</h1>
            
            {success_message}
            
            <form method="POST" action="/admin/config">
                <div class="config-form">
                    {"".join(sections_html)}
                </div>
                
                <div class="button-group">
                    <button type="button" class="btn btn-secondary" onclick="resetDefaults()">Reset to Defaults</button>
                    <button type="submit" class="btn btn-primary">💾 Save Configuration</button>
                </div>
            </form>
        </div>
        
        <script>
            // Update range value displays
            document.querySelectorAll('.form-range').forEach(range => {{
                const valueDisplay = range.nextElementSibling;
                range.addEventListener('input', () => {{
                    valueDisplay.textContent = range.value;
                }});
            }});
            
            // Reset to defaults function
            function resetDefaults() {{
                if (confirm('Are you sure you want to reset all settings to their default values?')) {{
                    window.location.href = '/admin/config/reset';
                }}
            }}
            
            // Form submission feedback
            document.querySelector('form').addEventListener('submit', function() {{
                const submitBtn = document.querySelector('.btn-primary');
                submitBtn.textContent = '💾 Saving...';
                submitBtn.disabled = true;
            }});
        </script>
    </body>
    </html>
    """
    
    return HTMLResponse(content=html)

@router.post("/config")
async def update_config(request: Request):
    """
    Handle form submission and update configuration values.
    """
    form_data = await request.form()
    
    # Process configuration parameters
    updated_config = {}
    for section_params in CONFIG_SECTIONS.values():
        for key in section_params:
            if key in form_data:
                values = form_data.getlist(key)
                
                # Handle multiselect (checkboxes return multiple values)
                if section_params[key].get("type") == "multiselect":
                    updated_config[key] = values
                elif len(values) == 1:
                    # Convert to appropriate type based on parameter definition
                    param_type = section_params[key].get("type", "text")
                    if param_type == "number" or param_type == "range":
                        try:
                            val_str = str(values[0])
                            if "." in val_str:
                                updated_config[key] = float(val_str)
                            else:
                                updated_config[key] = int(val_str)
                        except ValueError:
                            updated_config[key] = values[0]
                    else:
                        updated_config[key] = values[0]
    
    # Update runtime config
    for key, value in updated_config.items():
        runtime_config.set_config(key, value)
    
    # Save to .env file
    try:
        runtime_config.to_env_file(".env")
        print(f"✅ Configuration updated: {list(updated_config.keys())}")
    except Exception as e:
        print(f"❌ Error saving configuration: {e}")
    
    # Redirect back to config page with success message
    return RedirectResponse(url="/admin/config?saved=true", status_code=303)

@router.get("/config/reset")
async def reset_config():
    """
    Reset all configuration values to their defaults.
    """
    try:
        runtime_config.reset_to_defaults()
        runtime_config.to_env_file(".env")
        print("✅ Configuration reset to defaults")
    except Exception as e:
        print(f"❌ Error resetting configuration: {e}")
    
    return RedirectResponse(url="/admin/config?reset=true", status_code=303)

@router.get("/config/api")
async def get_config_api():
    """
    API endpoint to get current configuration as JSON
    """
    return {
        "config": runtime_config.all_config(),
        "sections": list(CONFIG_SECTIONS.keys())
    }
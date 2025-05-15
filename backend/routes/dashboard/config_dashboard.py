# config_dashboard.py
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from runtime_config import get as get_config, set as set_config, to_env_file

router = APIRouter()

CONFIG_KEYS = {
    "SESSION_MEMORY_CHAR_LIMIT": "Max characters in short-term memory",
    "GPT_MODEL": "Model (e.g. gpt-4, gpt-4o, gpt-3.5)",
    "PROMPT_HISTORY_DEPTH": "Prompt history depth (messages)",
    "TONE_STYLE": "Tone style label (e.g. empathetic, casual)"
}

@router.get("/config", response_class=HTMLResponse)
async def config_dashboard():
    rows = "".join([
        f"<label><strong>{label}:</strong><br><input name=\"{key}\" value=\"{get_config(key)}\" size=50></label><br><br>"
        for key, label in CONFIG_KEYS.items()
    ])

    return HTMLResponse(f"""
        <html><body style='font-family:sans-serif;padding:2rem;'>
        <h2>Mobeus Assistant — Config Dashboard</h2>
        <form method='POST'>
        {rows}
        <button type='submit'>Save Config</button>
        </form>
        </body></html>
    """)

@router.post("/config")
async def update_config(request: Request):
    form = await request.form()
    for key in CONFIG_KEYS:
        val = form.get(key)
        if val:
            set_config(key, val)
    to_env_file(".env")
    return RedirectResponse(url="/config", status_code=303)
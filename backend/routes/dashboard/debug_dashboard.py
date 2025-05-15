import os
import json
import shutil
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from config import DEBUG_LOG_PATH

router = APIRouter()

@router.get("/debug", response_class=HTMLResponse)
def get_debug_log():
    log_path = os.getenv("MOBEUS_DEBUG_LOG", "rag_debug_fresh.jsonl")

    # If it’s a directory instead of a file, delete it
    if os.path.isdir(log_path):
        shutil.rmtree(log_path)

    # If it doesn't exist, create a blank log file
    if not os.path.exists(log_path):
        with open(log_path, "w") as f:
            f.write("")
        return HTMLResponse("<h2>Log file was missing. Created new empty log file.</h2>", status_code=200)

    try:
        with open(log_path, "r") as f:
            lines = f.readlines()
            if not lines:
                return HTMLResponse("<h2>Log file is empty.</h2>", status_code=200)

        html = ["<h1>Mobeus Debug Log</h1>"]
        for line in reversed(lines[-50:]):
            try:
                entry = json.loads(line)
                ts = entry.get("timestamp", "")
                query = entry.get("query", "")
                answer = entry.get("answer", "")
                html.append(f"<div><strong>{ts}</strong>: <em>{query}</em><br><pre>{answer}</pre></div><hr>")
            except json.JSONDecodeError:
                html.append("<div><em>Malformed log entry</em></div><hr>")

        return HTMLResponse("".join(html), status_code=200)

    except Exception as e:
        return HTMLResponse(f"<h2>Error reading log file: {e}</h2>", status_code=500)

    html = [
        "<head><title>Mobeus Assistant — Debug Log</title><style>",
        "body{font-family:sans-serif;padding:2rem;background:#f9f9f9}",
        "h1{margin-bottom:1rem}pre{background:#eee;padding:1rem;border-radius:6px;white-space:pre-wrap;word-break:break-word;overflow-x:auto;max-width:100%;display:block}",
        "details{border:1px solid #ccc;border-radius:8px;padding:1rem;background:#fff;margin-bottom:1rem}",
        "details summary{font-weight:bold;font-size:1rem;cursor:pointer;margin-bottom:0.5rem}",
        "details[open] summary::after{content:' ▲'}details summary::after{content:' ▼'}",
        ".metric{display:inline-block;margin-right:1rem;padding:0.3rem 0.5rem;border-radius:4px;background:#f0f0f0;margin-bottom:0.5rem}",
        ".good{color:green}.warning{color:orange}.bad{color:red}",
        ".metrics-grid{display:grid;grid-template-columns:repeat(auto-fill, minmax(180px, 1fr));gap:0.5rem}",
        "</style></head><body><h1>Mobeus Assistant — Debug Log</h1>",
        "<div style='margin-bottom:1rem'>",
        "<p><strong>Performance Targets:</strong> ",
        "<span class='metric good'>GPT &lt; 3s</span> ",
        "<span class='metric good'>TTS First Chunk &lt; 1.5s</span> ",
        "<span class='metric good'>Total &lt; 5s</span>",
        "</p></div>"
    ]

    try:
        with open(log_path, "r") as f:
            lines = reversed(f.readlines()[-50:])
    except Exception:
        return HTMLResponse("<h2>Error reading log file.</h2>", status_code=500)

    for line in lines:
        try:
            entry = json.loads(line)
            ts = entry.get("timestamp", "")
            q = entry.get("query", "")
            a = entry.get("answer", "")
            timings = entry.get("timings", {})
            chunks = entry.get("top_chunks", [])
            html.append(f"<details><summary><strong>{ts}</strong> — <em>{q}</em></summary><div>")
            html.append(f"<strong>Answer:</strong><br><pre>{a}</pre>")

            if timings:
                html.append("<strong>Performance Metrics:</strong>")
                html.append("<div class='metrics-grid'>")

                def format_metric(name, value, unit="s", thresholds=None):
                    if value is None:
                        return f"<div class='metric'><strong>{name}:</strong> N/A</div>"
                    if thresholds is None:
                        thresholds = (3.0, 5.0) if name == "gpt" else (2.0, 4.0)
                    color = "good" if value <= thresholds[0] else "warning" if value <= thresholds[1] else "bad"
                    val = f"{value:.2f}" if isinstance(value, float) else value
                    return f"<div class='metric {color}'><strong>{name}:</strong> {val}{unit}</div>"

                for key, val in timings.items():
                    html.append(format_metric(key, val))
                html.append("</div>")

            html.append("<strong>Top Chunks:</strong><br><pre>" + json.dumps(chunks, indent=2) + "</pre>")
            html.append("<details><summary style='margin-top:1rem'>🔍 RAW JSON</summary><pre>" + line + "</pre></details>")
            html.append("</div></details>")
        except Exception as e:
            html.append(f"<p>Error parsing line: {e}</p>")

    html.append("</body>")
    return HTMLResponse(content="".join(html), status_code=200)

# ✅ Mobeus RAG Deployment Checklist + Troubleshooting Guide

This guide outlines the full, safe redeployment process for the Mobeus RAG stack. Includes pre-deploy prep, command-line steps, and real-world gotchas from past experience.

---

## 🚀 Standard Deployment Steps (from Local to Server)

### 1. Commit and Push All Local Changes

```bash
git status
git add .
git commit -m "🛠 Feature: <short description>"
git push origin main
```

---

### 2. SSH into Server and Pull Latest

```bash
ssh ubuntu@<your-server-ip>
cd ~/mobeus-rag
git pull origin main
```

If blocked by uncommitted files (e.g. `rag_debug_fresh.jsonl`):

```bash
rm rag_debug_fresh.jsonl
git pull origin main
```

---

### 3. Rebuild Docker Containers

```bash
docker-compose down
docker-compose up -d --build
```

---

### 4. Rebuild Frontend (if needed)

If React frontend code changed:

```bash
cd frontend
npm run build
```

---

### 5. Smoke Test

```bash
curl -i -X POST https://rag.mobeus.ai/api/stream-query   -H "Content-Type: application/json"   -d '{"query": "test"}'
```

Confirm:

- ✅ `https://rag.mobeus.ai` loads the app
- ✅ `/api/debug` renders the dashboard
- ✅ Streaming works with low latency

---

## 🧯 Troubleshooting Gotchas

### ❌ 404 on `/api/stream-query`

- Route not registered in FastAPI
- Confirm route is `@app.get("/api/stream-query")` or `include_router(..., prefix="/api")`
- FastAPI didn’t rebuild → run `docker-compose up -d --build`

---

### ❌ 502 from NGINX

- Missing or wrong Docker DNS resolver
- Fix in NGINX config: `resolver 127.0.0.11;`
- Add: `proxy_http_version 1.1;` and `proxy_buffering off;` for streaming routes

---

### ❌ NGINX not using correct config

- You mounted `nginx.conf` instead of `default.conf`
- Fix: use `./nginx/default.conf:/etc/nginx/conf.d/default.conf` in `docker-compose.yml`

---

### ❌ HTTPS doesn't work or curl gives connection refused

- Port 443 not exposed → add to `docker-compose.yml`:
  ```yaml
  ports:
    - "443:443"
  ```
- Host NGINX still running → disable it:
  ```bash
  sudo systemctl stop nginx
  ```

---

### ❌ React app shows old version

- You forgot to run `npm run build` after frontend changes
- Or browser cached `/frontend/dist`
- Clear cache or rebuild

---

## 🏷 Tag a Stable Checkpoint (Optional)

```bash
git tag -a v1.0.0-stable -m "🔖 Stable: deployed live with HTTPS and debug"
git push origin --tags
```

---

## 🧪 Dev Mode Tips

To use Vite live dev server:

```bash
npm run dev -- --host
```

Then access via:

```
http://<server-ip>:5173
```

---

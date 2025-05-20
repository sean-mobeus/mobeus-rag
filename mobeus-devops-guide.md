# 🧠 Mobeus Site: Local + Production NGINX & Docker Setup Guide

This guide documents a clean, robust setup for running Mobeus locally and in production using Docker and NGINX.

Our frontend uses VITE_API_BASE=/api to keep it environment-agnostic.
In dev, Vite proxies /api to http://localhost:8010.
In production, NGINX does the same.
This allows consistent code across all environments with no hardcoded URLs.

Our backend routes are mounted under /api, so /api/query must be preserved.
If we rewrite it to /query, FastAPI will 404.
Our Vite proxy does exactly what we need: it passes /api/\* through as-is to the backend on port 8010.
Stripping /api only makes sense if the backend expects flat /query, which ours does not.

---

## ✅ Directory Structure

```bash
mobeus-site/
├── backend/
├── frontend/
├── nginx/
│   ├── default.conf     # Production (SSL) config
│   ├── zz_dev.conf      # Local dev-only config
│   └── nginx.conf       # (Optional, unused now)
├── docker-compose.yml   # Main (production-ready) config
├── docker-compose.override.yml  # Local dev override
```

---

## 🚀 Deployment Setup (Production)

### Uses:

- `docker-compose.yml`
- NGINX + SSL (`default.conf`)
- Mounted letsencrypt certs

### Key lines in `docker-compose.yml`:

```yaml
services:
  nginx:
    ports:
      - "8080:80"
      - "443:443"
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf
      - /etc/letsencrypt:/etc/letsencrypt:ro
```

---

## 🧪 Local Dev Setup

### Uses:

- `docker-compose.override.yml`
- NGINX no-SSL (`zz_dev.conf`)
- No port 443
- No /etc/letsencrypt volume

### `docker-compose.override.yml`

```yaml
services:
  nginx:
    ports:
      - "8080:80"
    volumes:
      - ./nginx/zz_dev.conf:/etc/nginx/conf.d/default.conf
```

### `nginx/zz_dev.conf`

```nginx
server {
  listen 80;
  server_name localhost;

  location /api/ {
    proxy_pass http://backend:8010;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
  }

  location / {
    root /var/www/html;
    index index.html;
    try_files $uri /index.html;
  }
}
```

---

## 💥 Troubleshooting Gotchas

### ❌ `BIO_new_file() failed` SSL cert error

> Caused by `/etc/letsencrypt` mount when certs don't exist

✅ Fix:

- Use `zz_dev.conf` locally
- Never mount `/etc/letsencrypt` in dev
- Comment out `ssl_certificate` lines

---

### ❌ NGINX won't start: "Is a directory"

> Caused when Docker creates a **directory** instead of a **file mount**

✅ Fix:

- Ensure `zz_dev.conf` exists (`touch nginx/zz_dev.conf`)
- Do not mount missing files
- Avoid empty volume paths

---

### ❌ Port 5173 already in use

> Happens when Vite dev server and Docker both try to use 5173

✅ Fix:

- Don’t expose `5173` in `docker-compose.override.yml` unless you’re running frontend in Docker
- Use `npm run dev -- --host` locally

---

## ✅ Summary: Clean Local Dev Flow

```bash
# Local development
docker-compose down --remove-orphans
docker-compose up -d --build
npm run dev -- --host  # for frontend
```

✅ All services up  
✅ No SSL or port conflicts  
✅ Easy to push to server with no edits

---

Keep building. This setup is now bulletproof 🔐

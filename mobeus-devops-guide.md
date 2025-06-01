# 🧠 Mobeus Site: Consistent Local + Production Docker Setup Guide

This guide documents a consistent setup for running Mobeus locally and in production using the **same Docker configuration** with environment-specific nginx configs.

**Philosophy**: Keep dev and production identical to avoid deployment surprises. Use Docker nginx with different configs for local (HTTP) vs production (HTTPS).

Our frontend uses VITE_API_BASE=/api to keep it environment-agnostic.
In dev, Vite proxies /api to http://localhost:8010.
In production, you can optionally use nginx for SSL/load balancing.

Our backend routes are mounted under /api, so /api/query works directly.
Admin dashboard is available at /admin/ with all sub-dashboards.

---

## ✅ Consistent Directory Structure

```bash
mobeus-site/
├── backend/
├── frontend/
├── nginx/
│   ├── default.conf         # Production (HTTPS + SSL)
│   └── zz_dev.conf         # Local dev (HTTP only)
├── docker-compose.yml       # Base config (same everywhere)
└── docker-compose.override.yml  # Local dev overrides
```

---

## 🚀 Base Docker Setup (Same Everywhere)

### docker-compose.yml (production-ready base):

```yaml
services:
  backend:
    container_name: backend
    build: ./backend
    ports:
      - "8010:8010"
    volumes:
      - ./backend:/app
      - ./docs:/app/docs
      - ./chroma:/app/chroma
      - ./logs:/app/logs
      - ./init-db:/app/init-db # Database initialization scripts
    env_file:
      - .env
    environment:
      PYTHONUNBUFFERED: "1"
      POSTGRES_HOST: postgres
      MOBEUS_DEBUG: "true"
    depends_on:
      - postgres

  frontend:
    build: ./frontend
    ports:
      - "5173:5173"

  nginx:
    image: nginx:latest
    ports:
      - "8080:80" # Main app
      - "443:443" # HTTPS (production)
      - "8088:8088" # Admin dashboard
    volumes:
      - ./nginx/default.conf:/etc/nginx/conf.d/default.conf # Production config
      - ./frontend/dist:/var/www/html
      - /etc/letsencrypt:/etc/letsencrypt:ro # SSL certificates (production)
    depends_on:
      - backend
      - frontend

  postgres:
    image: postgres:15-alpine
    restart: always
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: password
      POSTGRES_DB: mobeus
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db:/docker-entrypoint-initdb.d # Database initialization

volumes:
  postgres_data:
```

---

## 🧪 Local Development Override

### docker-compose.override.yml (local dev only):

```yaml
services:
  nginx:
    ports:
      - "8080:80" # HTTP only (no 443)
      - "8088:8088" # Admin dashboard
    volumes:
      # Use local HTTP-only config instead of production HTTPS
      - ./nginx/zz_dev.conf:/etc/nginx/conf.d/default.conf
      # Remove SSL certificate mount (not needed locally)

  backend:
    environment:
      - MOBEUS_DEBUG=true
```

### nginx/zz_dev.conf (local HTTP):

```nginx
# Main app server (HTTP only)
server {
    listen 80;
    server_name localhost;

    # Chat endpoints (WebSocket and HTTP) to backend
    location /chat/ {
        proxy_pass http://backend:8010/chat/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API routes to backend
    location /api/ {
        proxy_pass http://backend:8010/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend static files
    location / {
        root /var/www/html;
        index index.html;
        try_files $uri /index.html;
    }
}

# Admin dashboard server
server {
    listen 8088;
    server_name localhost;

    # Admin routes to backend
    location / {
        proxy_pass http://backend:8010/admin/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 🏭 Production Deployment

### nginx/default.conf (production HTTPS):

```nginx
# HTTP to HTTPS redirect
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# Main app server (HTTPS)
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Chat endpoints (WebSocket and HTTP) to backend
    location /chat/ {
        proxy_pass http://backend:8010/chat/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API routes to backend
    location /api/ {
        proxy_pass http://backend:8010/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Frontend static files
    location / {
        root /var/www/html;
        index index.html;
        try_files $uri /index.html;
    }
}

# Admin dashboard server (HTTPS)
server {
    listen 8088 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Admin routes to backend
    location / {
        proxy_pass http://backend:8010/admin/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### Production Access Points:

- **Main App**: https://yourdomain.com
- **Admin Dashboard**: https://yourdomain.com:8088
- **API**: https://yourdomain.com/api/

---

## ✅ Local Development (two workflows)

You can develop locally either with Docker‑based static serving (via nginx) or with the Vite dev server (HMR).

### Option 1: Docker‑based local dev (static SPA + nginx)

```bash
# Build frontend production assets for nginx
cd frontend
npm install
npm run build
cd ..

# Start services (nginx, backend, database, etc.)
docker-compose up -d

# Inspect as needed
docker-compose ps
docker-compose logs nginx
docker-compose logs backend
```

Open in browser:

- Main App: http://localhost:8080
- Admin Dashboard: http://localhost:8088
- API: http://localhost:8080/api/

### Option 2: Vite dev server (fast HMR, no nginx)

```bash
# Start backend services (database, Redis, etc.) without nginx
docker-compose up -d backend db redis

# Launch FastAPI on port 8010
uvicorn backend.main:app --reload --port 8010

# From the frontend directory, set your backend URL and start Vite
export VITE_BACKEND_BASE_URL=http://localhost:8010
cd frontend
npm install
npm run dev
```

Open in browser:

- Frontend (Vite dev server): http://localhost:5173
- API: http://localhost:8010/api/
- Admin UI: http://localhost:8010/admin/

---

## 💥 Problems This Solves

### ❌ "Works locally but breaks in production"

✅ **Fixed**: Same Docker setup, same nginx routing, same volume mounts

### ❌ "Different configs between environments"

✅ **Fixed**: Only nginx config file differs (HTTP vs HTTPS)

### ❌ "Database initialization doesn't work on server"

✅ **Fixed**: `init-db` volume mount consistent everywhere

### ❌ "SSL works in production but I can't test nginx routing locally"

✅ **Fixed**: Test nginx routing locally with HTTP, production uses HTTPS

---

## 🎯 Benefits of This Approach

✅ **Consistent Environments**: Identical Docker setup everywhere  
✅ **Easy Deployment**: Same docker-compose.yml, just different nginx config  
✅ **SSL Ready**: Production HTTPS, local HTTP (no cert needed)  
✅ **Database Initialization**: init-db scripts work everywhere  
✅ **Easy Debugging**: Can access backend directly when needed  
✅ **No Config Drift**: Same ports, same volumes, same services

## 🚀 Deployment Commands

### Local Development:

```bash
docker-compose up -d                    # Uses override for HTTP
docker-compose logs -f backend         # View backend logs
```

### Production Deployment:

```bash
# Remove override file (uses production HTTPS config)
rm docker-compose.override.yml        # Or rename it
docker-compose up -d --build          # Deploy with HTTPS
```

---

Keep building. This setup is now bulletproof AND simple 🔐

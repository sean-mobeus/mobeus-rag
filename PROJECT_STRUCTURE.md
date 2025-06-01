# Project Structure

This document provides a high-level overview of the project directory layout and key files to help onboard new developers.

```
.
├── backend/                   # Python FastAPI backend (modular services & refactor guide)
├── frontend/                  # Vite-based single-page application client
├── nginx/                     # Nginx reverse proxy configuration (HTTP & HTTPS)
├── php/                       # Sample/test PHP scripts
├── chroma/                    # Chroma vector DB data (auto-generated)
├── docs/                      # Project documentation (Word docs, JSONL configs, developer guides)
├── init-db/                   # Database initialization scripts
├── logs/                      # Application logs and debugging artifacts
├── tests/                     # Automated tests (pytest)
├── mobeus-devops-guide.md     # DevOps and Docker setup guide
├── docker-compose.yml         # Docker Compose orchestration for services
├── docker-compose.override.yml# Optional local development overrides
├── deployment-checklist.md    # Deployment checklist and environment setup
├── PROJECT_STRUCTURE.md       # This project structure guide
└── [misc files]               # .env, debug scripts, assets, etc.
```

---

## backend/
- **main.py**               FastAPI application entry point; registers routes and middleware.
- **refactor_guide.md**     Guide to modularize and refactor the monolithic backend.
- **requirements.txt**      Python dependencies.
- **Dockerfile**            Backend service container build.
- **config/**               Configuration management (runtime and environment settings).
- **routes/**               FastAPI routers delegating to service modules.
- **chat/**                 Chat orchestration, multi-agent logic, and tone control.
- **memory/**               Conversation context storage and persistent memory.
- **audio/**                Audio streaming and processing abstractions.
- **video/**                Video ingestion and processing (stubs and future features).
- **rag/**                  Retrieval-Augmented Generation (vector store client & retriever).
- **vector/**               Chunking and embedding logic for Retrieval-Augmented Generation.
- **voice_commands/**       Speech recognition and voice-command handling.
- **stats/**                Analytics, metrics collection, and dashboard APIs.
- **scripts/**              Utility scripts (DB init, test pipelines, logs setup).

## frontend/
- **README.md**           Frontend setup and development guide.
- **package.json**, **package-lock.json**  NPM project manifest and lockfile.
- **vite.config.js**      Vite bundler configuration.
- **tailwind.config.js**  Tailwind CSS configuration.
- **postcss.config.js**   PostCSS configuration.
- **eslint.config.js**    ESLint configuration.
- **src/**                Application source code (components, pages, state management).
- **public/**             Static assets (images, icons, favicon).
- **archive/**            Deprecated or experimental components kept for reference.
- **index.html**          HTML template and mounting point.
- **Dockerfile**          Frontend container build.

## nginx/
- Multiple `.conf` files for reverse proxy:
  - *nginx.conf*         Main Nginx configuration.
  - *default.conf*        Default server configuration.
  - *zz_dev.conf*         Development-specific proxy settings.

## php/
- **debug.php**           Example PHP debugging endpoint.
- **test.php**            Simple test script.

## chroma/
- Local Chroma vector database storage (SQLite and binary data). Auto-generated;
  typically not checked into version control.

## docs/
**technical_documentation.md** Developer-focused technical documentation with high-level summary introduction.
**Mobeus_Complete_Overview_Expanded_Fixed.docx**  Detailed project overview.
**Mobeus_Knowledge_Base.docx**                   Domain knowledge base.
**mobeus-source-content.docx**                   Source content for ingestion.
**tone_shaper.jsonl**                            JSONL config for tone shaping.

## mobeus/
- **__init__.py**         Python package initialization (currently stub).

## Top-Level Files
- **docker-compose.yml**               Orchestrate services (backend, frontend, nginx, vector DB).
- **docker-compose.override.yml**      Optional Docker Compose overrides for local development.
- **deployment-checklist.md**          Deployment checklist and environment setup.
- **Sprint 3 Kickoff.docx**            Sprint planning kickoff document.
- **Debug log files and artifacts**: debug_log.jsonl, rag_debug.jsonl, rag_debug_fresh.jsonl.
- **Audio samples and temp files**: response.mp3, temp_speech_*.mp3, test_audio.*.

---

Please refer to each subdirectory's README or inline comments for deeper implementation details and development workflows.

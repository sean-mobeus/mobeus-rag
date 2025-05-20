# Project Structure

This document provides a high-level overview of the project directory layout and key files to help onboard new developers.

```
.
├── backend/                   # Python FastAPI backend service
├── frontend/                  # Vite-based single-page application client
├── nginx/                     # Nginx reverse proxy configuration (multiple confs)
├── php/                       # Sample/test PHP scripts
├── chroma/                    # Chroma vector DB data (auto-generated)
├── docs/                      # Project documentation (Word docs, JSONL configs)
├── mobeus/                    # Python package stub (module initialization)
├── docker-compose.yml         # Docker Compose orchestration for services
├── docker-compose.override.yml# Optional local development overrides
├── deployment-checklist.md    # Deployment checklist and environment setup
├── Sprint 3 Kickoff.docx      # Sprint planning kickoff document
└── [misc files]               # Debug logs, audio samples, temporary assets
```

---

## backend/
- **main.py**             FastAPI app entrypoint, registers routes and middleware.
- **config.py**           Static and environment configuration.
- **runtime_config.py**   Runtime configuration loader (handles dynamic settings).
- **rag.py**              Retrieval-Augmented Generation logic (queries vector store and LLM).
- **memory/**             Session and persistent memory management modules.
  - *session_memory.py*     In-memory session-scoped memory for conversation state.
  - *persistent_memory.py*  Persistent memory storage across sessions.
  - *user_identity.py*      User identity and profile handling.
- **ingest/**             Data ingestion scripts for populating/updating the vector database.
  - *chunk_and_ingest.py*   Splits source documents into chunks and ingests them.
  - *ingest_tone.py*        Custom ingestion for tone-shaper data.
- **agents/**             Custom agent logic.
  - *prompt_orchestrator.py* Orchestrates prompts sent to the LLM.
  - *tone_engine.py*         Manages tone transformations.
- **routes/**             FastAPI router modules.
  - *streaming_rag.py*        Streaming RAG endpoint.
  - *speak_stream.py*         TTS streaming endpoint.
  - *user_identity_routes.py* User identity REST endpoints.
  └── **dashboard/**          Dashboards for runtime configuration and debugging.
      - *config_dashboard.py* UI & API for runtime config.
      - *debug_dashboard.py*  Debug logs and metrics dashboard.
- **tts/**                Text-to-speech implementation.
  - *streaming.py*          Uses OpenAI TTS APIs.
- **requirements.txt**    Python dependencies.
- **Dockerfile**          Backend service container build.

## frontend/
- **README.md**           Frontend setup and development guide.
- **package.json**, **package-lock.json**  NPM project manifest and lockfile.
- **vite.config.js**      Vite bundler configuration.
- **tailwind.config.js**  Tailwind CSS configuration.
- **postcss.config.js**   PostCSS configuration.
- **eslint.config.js**    ESLint configuration.
- **src/**                Application source code (components, pages, state management).
- **public/**             Static assets (images, icons, favicon).
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
- **Mobeus_Complete_Overview_Expanded_Fixed.docx**  Detailed project overview.
- **Mobeus_Knowledge_Base.docx**                   Domain knowledge base.
- **mobeus-source-content.docx**                   Source content for ingestion.
- **tone_shaper.jsonl**                            JSONL config for tone shaping.

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

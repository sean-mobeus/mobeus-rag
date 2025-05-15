# Project Structure

This document provides a high-level overview of the project directory layout and key files to help onboard new developers.

```
.
├── backend/           # Python FastAPI backend service
├── frontend/          # Vite-based single-page application client
├── nginx/             # Nginx reverse proxy configuration
├── php/               # Sample/test PHP scripts
├── chroma/            # Chroma vector DB data (auto-generated)
├── docs/              # Project documentation (Word docs, JSONL configs)
├── mobeus/            # Python package stub (module initialization)
├── docker-compose.yml # Docker Compose orchestration for services
├── Sprint 3 Kickoff.docx # Sprint planning kickoff document
└── [misc files]       # Debug logs, test audio files, temporary assets
```

---

## backend/
- **main.py**           FastAPI app entrypoint, registers routes and middleware.
- **config.py**         Configuration (API keys, paths, environment settings).
- **rag.py**            Retrieval-Augmented Generation logic (queries vector store and LLM).
- **ingest/**           Data ingestion scripts for populating/updating the vector database.
  - *chunk_and_ingest.py*  Splits source documents into chunks and ingests them.
  - *ingest_tone.py*      Custom ingestion for tone-shaper data.
- **agents/**           Custom agent logic (e.g., tone_engine.py manages tone transformations).
- **routes/**           FastAPI routers: streaming RAG (`streaming_rag.py`), TTS (`speak_stream.py`).
- **tts/**              TTS streaming implementation (uses OpenAI TTS APIs).
- **requirements.txt**  Python dependencies.
- **Dockerfile**        Backend service container build.

## frontend/
- **README.md**         Frontend setup and development guide.
- **package.json**      NPM project manifest (scripts, dependencies).
- **vite.config.js**, **tailwind.config.js**, **postcss.config.js**
  Configuration files for build, styling, and tooling.
- **src/**              Application source code (components, pages, state management).
- **public/**           Static assets (images, icons, favicon).
- **index.html**        HTML template and mounting point.
- **Dockerfile**        Frontend container build.

## nginx/
- **nginx.conf**        Reverse proxy configuration (routes traffic to backend and frontend).

## php/
- **debug.php**         Example PHP debugging endpoint.
- **test.php**          Simple test script.

## chroma/
- Local Chroma vector database storage (SQLite and binary data). Auto-generated;
  typically not checked into version control.

## docs/
- **Mobeus_Complete_Overview_Expanded_Fixed.docx**  Detailed project overview.
- **Mobeus_Knowledge_Base.docx**                   Domain knowledge base documents.
- **mobeus-source-content.docx**                   Source content for ingestion.
- **tone_shaper.jsonl**                             JSONL config for tone shaping.

## mobeus/
- **__init__.py**        Python package initialization (currently stub).

## Top-Level Files
- **docker-compose.yml** Docker Compose file to run backend, frontend, nginx, and vector DB.
- **Sprint 3 Kickoff.docx** Sprint planning document.
- **debug_log.jsonl**, **rag_debug.jsonl**, etc. Debug log files (can be ignored/archived).
- **test_audio.*.mp3/m4a** Example audio files for testing voice endpoints.

---
Please refer to each subdirectory's README or inline comments for deeper details on implementation and development workflows.
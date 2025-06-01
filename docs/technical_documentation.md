# Technical Documentation for Developers

## Introduction

Mobeus is an AI-driven chat platform that integrates real-time conversation, memory, audio/video processing, and retrieval-augmented generation. This document provides a high-level summary and technical details to help developers understand the architecture, core modules, and development workflow.

## Architecture Overview

The Mobeus site consists of three main components:

- **Backend**: A modular FastAPI service exposing REST and WebSocket endpoints for chat, memory, audio, video, RAG, voice commands, and analytics.
- **Frontend**: A Vite-based single-page application (SPA) that interacts with the backend via HTTP and WebSocket.
- **Infrastructure/DevOps**: Docker, Nginx, and PostgreSQL for consistent local and production deployments.

Refer to [PROJECT_STRUCTURE.md](../PROJECT_STRUCTURE.md) for a complete directory layout.

### Backend Components

Key modules under `backend/`:

- **config/**: Runtime and environment configuration management.
- **routes/**: FastAPI routers delegating to individual service modules.
- **chat/**: Chat orchestration, multi-agent workflows, and tone control.
- **memory/**: Session and persistent memory storage for conversation context.
- **audio/**: Audio streaming and speech processing abstractions.
- **video/**: Video ingestion and processing stubs for future features.
- **rag/**: Retrieval-Augmented Generation (vector store client and retriever).
- **vector/**: Chunking and embedding logic for Retrieval-Augmented Generation.
- **voice_commands/**: Speech recognition and voice-command handling.
- **stats/**: Analytics, metrics collection, and dashboard APIs.
- **scripts/**: Utility scripts (database initialization, testing pipelines, logs setup).
- **main.py**: FastAPI application entry point.

### Frontend Components

Frontend source under `frontend/src/` includes:

- UI components and pages.
- State management (e.g., React Context or Redux).
- API clients for REST and WebSocket communication.
- Static assets in `frontend/public/`.

Refer to `frontend/README.md` for setup and development instructions.

## Development Workflow

### Prerequisites

- Docker & Docker Compose
- Node.js (>=14.x)
- Python (>=3.9) and pip
- Git

### Local Setup

1. Clone the repository and copy `.env.example` to `.env`.
2. Build and start services with Docker:
   ```bash
   docker-compose up -d
   ```
3. Install frontend dependencies and start the Vite dev server:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```
4. Open the app at http://localhost:5173 and the admin dashboard at http://localhost:8088.

### Testing

- **Backend tests** use pytest:
  ```bash
  cd backend
  pytest
  ```
- **Frontend tests** (if configured) use the project's testing framework (e.g., Jest).

### Code Quality

- Format and lint code with the project's linters and formatters (e.g., black, flake8, ESLint, Prettier).
- Follow existing style and patterns when adding new code.
- Add unit and integration tests for new features.

## Deployment

Refer to [mobeus-devops-guide.md](../mobeus-devops-guide.md) for details on Docker-based deployment to local and production environments, including Nginx configurations and SSL setup.

## Contributing

Please open issues or pull requests on the repository. Follow commit message conventions and branch naming guidelines.

---

This document serves as a technical reference and onboarding guide for developers working on the Mobeus site.
# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A FastAPI-based backend for an HWP document Q&A system with RAG (Retrieval-Augmented Generation) capabilities, supporting Korean legal documents and user-uploaded files.

## Commands

### Development

```bash
# Install dependencies
uv pip install .

# Run development server
fastapi run
# or
.venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# Run with Docker (full stack: Postgres, Redis, Celery)
docker-compose up
```

### Background Workers

```bash
# Celery worker
.venv/bin/celery -A workers.celery_app worker -l info --concurrency=4

# Celery beat (scheduled tasks)
.venv/bin/celery -A workers.celery_app beat -l info
```

### Linting / Type Checking

```bash
ruff check .
ruff format .
basedpyright
```

### Production

```bash
docker-compose -f docker-compose.prod.yaml up
```

## Architecture

### Layer Structure

```
API (app/api/v1/) → Services (app/services/) → Models (app/models/) + DB (app/db/)
```

- **API layer** (`app/api/v1/`): FastAPI routers. Each domain (auth, chat, documents, groups, users) has its own subdirectory.
- **Services layer** (`app/services/`): Business logic. Services receive DB sessions and return domain objects or raise `BackendBaseError` subclasses.
- **Models** (`app/models/`): SQLModel classes that serve as both ORM tables and Pydantic models.
- **Schemas** (`app/schemas/`): Request/response Pydantic models separate from ORM models.
- **Errors** (`app/errors/`): Custom `BackendBaseError` subclasses per domain. The main app registers a single handler in `app/main.py` that serializes these to JSON responses.

### RAG Pipeline (`app/rag/`)

Multi-source semantic search over three domains:
1. **Private documents** — user/group-uploaded files chunked and embedded into pgvector
2. **Korean laws (공법)** — indexed from legal databases
3. **Korean precedents (판례)** — crawled and indexed

Key files:
- `rag/agent.py` — LangChain agent that routes queries to appropriate search tools
- `rag/model.py` — LLM + embedding model setup (Ollama with BGE-M3 embeddings)
- `rag/tools.py` — LangChain tools wrapping each search domain
- `rag/search.py` — pgvector similarity search implementations

### Background Jobs (`app/workers/`)

Celery with Redis broker. The worker process also initializes a JVM (via Jpype) for HWP document processing.

Scheduled tasks (defined in `celery_app.py`):
- `update-rag-daily-task` — daily at 4 AM
- `process-json-precedents-task` — runs on a fixed schedule

### Database

- PostgreSQL with pgvector extension
- SQLModel ORM (SQLAlchemy 2.0 under the hood)
- Both sync and async engines defined in `app/db/session.py`
- Soft deletes via `deleted_at` timestamp on most models
- Vector embeddings stored in `document_chunk` table

### Authentication

- JWT access tokens + refresh tokens (stored in DB)
- Google OAuth 2.0 integration
- Auth utilities in `app/utils/auth.py`

## Key Environment Variables

See `.env.example` for the full list. Critical ones:

| Variable | Purpose |
|---|---|
| `POSTGRES_*` | Database connection |
| `JWT_SECRET_KEY` | Token signing |
| `OLLAMA_BASE_URL` | LLM server URL |
| `AWS_*` | S3 document storage |
| `REDIS_URL` | Celery broker |
| `ENVIRONMENT` | `development` or `production` (controls SQL echo, etc.) |

## Conventions

- All API routes are prefixed with `/v1/`
- Errors are raised as domain-specific `BackendBaseError` subclasses (never return error dicts manually)
- Document scope can be `private`, `group`, or `public`
- Chat spaces can be owned by a user or a group

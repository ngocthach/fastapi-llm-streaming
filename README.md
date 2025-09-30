# FastAPI LLM Streaming Service

A simple, reliable backend service that streams responses from an LLM, stores conversation history, and exposes history APIs.

## Tech Stack
- FastAPI (Python)
- Async SQLAlchemy + asyncpg (PostgreSQL)
- Alembic (migrations)
- Optional: OpenAI for real LLM streaming

## Getting Started (local)

1. Create and activate virtual env (already present at `src/backend/venv` in this repo).
2. Configure environment:
   - Copy `src/backend/.env.example` to `src/backend/.env` and update values
3. Install dependencies:
   - `src/backend/venv/bin/python -m pip install -r src/backend/requirements.txt`
4. Run database migrations:
   - `cd src/backend && ../venv/bin/python -m alembic upgrade head`
5. Start the app:
   - `cd src/backend && ../venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`

## API

- Health
  - GET `/health`
- Streaming
  - POST `/stream`
    - body: `{ "prompt": "some text" }`
    - query: `stream_format=text|openai` (default `text`)
      - `text`: streams plain text
      - `openai`: streams minimal OpenAI-like JSON lines per chunk
- History
  - GET `/history?limit=10&offset=0`
  - GET `/history/{id}`
- Search
  - GET `/search?query=...&limit=10&offset=0`
    - PostgreSQL full-text search across prompt and response, ranked by relevance


## Authentication, Rate Limiting, Logging

- Optional API key auth: set `API_KEY` in `.env`; clients send `X-API-Key: <value>`
- In-memory rate limiting: configurable via `.env` (enabled by default)
  - `RATE_LIMIT_ENABLED`, `RATE_LIMIT_REQUESTS`, `RATE_LIMIT_WINDOW_SECONDS`
- Structured logging: JSON log lines with request correlation ID (`X-Request-ID`)

## Configuration (.env)

- Database: `POSTGRES_*` or `DATABASE_URL`
- OpenAI: `OPENAI_API_KEY` (if missing, the app uses a mock LLM stream)
- Logging: `LOG_JSON=true|false`
- Auth: `API_KEY=<token>` (omit to disable)
- Rate limiting: see variables above

## cURL quickstart

Note: Include `-H "X-API-Key: $API_KEY"` if you configured an API key.

- Health
```bash
curl -s http://localhost:8000/health | jq
```

- Stream (plain text)
```bash
curl -N -s http://localhost:8000/stream \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Hello there"}'
```

- Stream (OpenAI-like JSON lines)
```bash
curl -N -s 'http://localhost:8000/stream?stream_format=openai' \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Tell me a joke"}' | jq -c '.'
```

- History (list)
```bash
curl -s 'http://localhost:8000/history?limit=10&offset=0' | jq
```

- History (by id)
```bash
curl -s 'http://localhost:8000/history/<uuid>' | jq
```

- Search (Postgres full-text search)
```bash
curl -s 'http://localhost:8000/search?query=foobar&limit=10&offset=0' | jq
```

## Docker (optional)

From `src/backend`:

```bash
# build & run app + postgres
docker compose up --build
# then run migrations in the app container (first time)
docker exec -it llm-streaming-app alembic upgrade head
```

Configure DB via `.env` in `src/backend`. If you already have a DB, you can comment out the `db` service in `docker-compose.yml` and just run the app.

## Document: Reviewing your Work

### Design and decisions
- Async-first: HTTP streaming and DB use asyncio for efficient concurrency
- Persistence guarantees: conversation content is persisted after streaming completes; on exceptions mid-stream, partial text is saved
- LLM abstraction: uses OpenAI when `OPENAI_API_KEY` is set, otherwise a mock streamer; same interface for both
- Error handling & retries: OpenAI stream acquisition has basic retry logic (in llm.py)
- Security: optional API key auth via `X-API-Key`
- Rate limiting: in-memory sliding window with `X-RateLimit-*` headers
- Observability: structured JSON logs and `X-Request-ID` for correlation
- Search: PostgreSQL full-text search endpoint with ranking

### Potential improvements
- Streaming transport: add Server-Sent Events (SSE) option and final [DONE] sentinel
- Enriched OpenAI-style chunks: include id/object/model/created/choices finish chunks by default
- Search performance: add a GIN index on `to_tsvector('english', prompt || ' ' || response)` via Alembic migration
- Query semantics: use `websearch_to_tsquery` and configurable language (e.g., `lang=en`)
- Rate limiting: move to Redis-backed limiter with per-route and per-user policies
- Observability: add tracing (OpenTelemetry), structured logs to a central sink
- Robustness: map errors to consistent API responses; timeouts/cancellation for model calls
- CI & QA: add CI to run tests, type checks, linters; add more unit/integration tests
- Security: per-user API keys, RBAC, audit logs; optional JWT auth


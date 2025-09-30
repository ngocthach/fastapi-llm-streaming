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
    - returns: streamed plain text
- History
  - GET `/history?limit=10&offset=0`
  - GET `/history/{id}`

## Docker (optional)

From `src/backend`:

```bash
# build & run app + postgres
docker compose up --build
# then run migrations in the app container (first time)
docker exec -it llm-streaming-app alembic upgrade head
```

Configure DB via `.env` in `src/backend`. If you already have a DB, you can comment out the `db` service in `docker-compose.yml` and just run the app.

## Design Notes
- Async-first design: HTTP streaming and DB are async
- Persistence guarantees: conversation is saved even on mid-stream errors (partial)
- LLM abstraction: falls back to mock unless `OPENAI_API_KEY` is set

## Future Improvements
- Auth (API token)
- Rate limiting
- Search endpoint (full-text search)
- Metrics/monitoring
- Robust error mapping and structured logs


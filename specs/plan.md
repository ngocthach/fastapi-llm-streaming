# Implementation Plan

## Technical Architecture

### Technology Stack

* **Frontend**: Not required for this assignment (could use cURL or Postman for testing).
* **Backend**: Python (FastAPI), async streaming with `httpx` or `asyncio`.
* **Database**: PostgreSQL (via SQLAlchemy + Alembic for migrations).
* **Containerization (optional bonus)**: Docker + Docker Compose.

### System Design

**Flow description**:

1. Client sends POST request with `{"prompt": "some text"}` to `/stream`.
2. FastAPI backend calls LLM provider (mocked or via OpenAI API) and streams response chunk-by-chunk back to client.
3. Once streaming completes, the service persists the **prompt, full response, timestamp** into PostgreSQL.
4. `/history` endpoint allows retrieval of past conversations.

**Architecture Diagram (textual)**:

```
Client → FastAPI Service → LLM Provider API
                 ↓
             PostgreSQL
```

### Database Schema

**Table: conversations**

* `id` (UUID, primary key)
* `prompt` (TEXT, not null)
* `response` (TEXT, not null)
* `created_at` (TIMESTAMP, default now)

Indexes:

* Index on `created_at` for history queries.

### API Design

* **POST /stream**

  * Input: `{"prompt": "some text"}`
  * Output: streamed response (text chunks)
  * After completion → saves to DB

* **GET /history**

  * Query params: `limit`, `offset`
  * Output: list of `{id, prompt, response, created_at}`

* **GET /history/{id}**

  * Output: single conversation record

---

## Development Phases

### Phase 1: Foundation

* Initialize FastAPI project structure
* Setup PostgreSQL + SQLAlchemy + Alembic migrations
* Define `conversations` table schema

### Phase 2: Core Features

* Implement `/stream` endpoint with chunked responses
* Persist conversation after streaming completes
* Implement `/history` (list + detail) endpoints
* Add error handling (bad request, LLM errors, DB failures)

### Phase 3: Polish

* Add logging & monitoring
* Add simple request validation (Pydantic models)
* Add documentation (README, design decisions, potential improvements)
* Containerize with Docker (bonus)
* Optional: implement conversation search (full-text search in PostgreSQL)

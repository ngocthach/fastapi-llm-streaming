import pytest
import httpx
from app.main import app

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.database import get_db


@pytest.fixture(autouse=True)
async def override_db_dep():
    # Create a fresh engine/session bound to the current test loop
    from app.config import get_settings
    url = get_settings().database_url
    engine = create_async_engine(url, echo=False, future=True)
    TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autocommit=False, autoflush=False)

    async def _get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = _get_db
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()
@pytest.fixture(autouse=True)
async def reset_rate_store():
    # Ensure rate limiter store is clean each test
    from app import middleware as mw
    mw._rate_store.clear()
    yield


@pytest.mark.asyncio
async def test_health_ok():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] in {"connected", "disconnected"}


@pytest.mark.asyncio
async def test_stream_and_history_flow():
    prompt = "pytest prompt"
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        # Stream
        r = await client.post("/stream", json={"prompt": prompt})
        assert r.status_code == 200
        assert isinstance(r.text, str) and len(r.text) > 0

        # History list
        r = await client.get("/history", params={"limit": 5, "offset": 0})
        assert r.status_code == 200
        body = r.json()
        assert "conversations" in body and isinstance(body["conversations"], list)
        assert body["total"] >= 1
        if body["conversations"]:
            item = body["conversations"][0]
            assert "id" in item and "prompt" in item and "response" in item and "created_at" in item
            rid = item["id"]
            r = await client.get(f"/history/{rid}")
            assert r.status_code == 200
            detail = r.json()
            assert detail["id"] == rid


@pytest.mark.asyncio
async def test_auth_middleware():
    from app.config import get_settings
    settings = get_settings()
    old = settings.api_key
    settings.api_key = "secret-key"
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/health")
            assert r.status_code == 401
            r = await client.get("/health", headers={"X-API-Key": "secret-key"})
            assert r.status_code == 200
    finally:
        settings.api_key = old


@pytest.mark.asyncio
async def test_rate_limit_middleware():
    from app.config import get_settings
    settings = get_settings()
    old_enabled, old_limit, old_window = settings.rate_limit_enabled, settings.rate_limit_requests, settings.rate_limit_window_seconds
    settings.rate_limit_enabled = True
    settings.rate_limit_requests = 1
    settings.rate_limit_window_seconds = 60
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.get("/health")
            assert r1.status_code == 200
            r2 = await client.get("/health")
            assert r2.status_code == 429
            assert r2.headers.get("X-RateLimit-Limit") == "1"
            assert r2.headers.get("X-RateLimit-Remaining") == "0"
    finally:
        settings.rate_limit_enabled = old_enabled
        settings.rate_limit_requests = old_limit
        settings.rate_limit_window_seconds = old_window

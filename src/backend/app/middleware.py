"""HTTP middlewares: request ID, auth, rate limiting, structured logging."""
import json
import logging
import time
import uuid
import contextvars
from typing import Callable, Dict, Tuple
from fastapi import Request
from fastapi.responses import JSONResponse
from app.config import get_settings

logger = logging.getLogger("app")
request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")

# Simple in-memory rate limiter storage: key -> (reset_epoch, count)
_rate_store: Dict[str, Tuple[float, int]] = {}


def _client_key(request: Request) -> str:
    # Prefer X-Forwarded-For when present; else use client host; else anon
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return (request.client.host if request.client else "anon")


async def request_context_middleware(request: Request, call_next: Callable):
    # Assign a request ID and propagate in context + response header
    rid = request.headers.get("x-request-id") or str(uuid.uuid4())
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        request_id_var.reset(token)


async def auth_middleware(request: Request, call_next: Callable):
    settings = get_settings()
    if settings.api_key:
        provided = request.headers.get("x-api-key", "")
        if provided != settings.api_key:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
    return await call_next(request)


async def rate_limit_middleware(request: Request, call_next: Callable):
    settings = get_settings()
    if not settings.rate_limit_enabled:
        return await call_next(request)

    key = _client_key(request)
    now = time.time()
    window = settings.rate_limit_window_seconds
    limit = settings.rate_limit_requests

    reset, count = _rate_store.get(key, (now + window, 0))
    # Reset window if expired
    if now > reset:
        reset = now + window
        count = 0
    count += 1

    remaining = max(0, limit - count)
    _rate_store[key] = (reset, count)

    if count > limit:
        # Over limit
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded"},
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": str(0),
                "X-RateLimit-Reset": str(int(reset)),
            },
        )

    response = await call_next(request)
    response.headers.update(
        {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(reset)),
        }
    )
    return response


async def logging_middleware(request: Request, call_next: Callable):
    settings = get_settings()
    start = time.perf_counter()
    rid = request_id_var.get("")
    try:
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": "INFO",
            "method": request.method,
            "path": request.url.path,
            "status": getattr(response, "status_code", None),
            "duration_ms": round(duration_ms, 2),
            "length": response.headers.get("content-length", "-"),
            "request_id": rid,
        }
        if settings.log_json:
            logger.info(json.dumps(record, ensure_ascii=False))
        else:
            logger.info(
                "method=%s path=%s status=%s duration_ms=%.2f length=%s request_id=%s",
                record["method"], record["path"], record["status"], record["duration_ms"], record["length"], record["request_id"],
            )
        return response
    except Exception as e:
        duration_ms = (time.perf_counter() - start) * 1000
        record = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "level": "ERROR",
            "method": request.method,
            "path": request.url.path,
            "error": repr(e),
            "duration_ms": round(duration_ms, 2),
            "request_id": rid,
        }
        if settings.log_json:
            logger.error(json.dumps(record, ensure_ascii=False))
        else:
            logger.exception(
                "method=%s path=%s error=%s duration_ms=%.2f request_id=%s",
                request.method, request.url.path, repr(e), duration_ms, rid,
            )
        raise


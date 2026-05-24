from __future__ import annotations
import time
import json
import secrets
import asyncio
import logging
from contextlib import asynccontextmanager
from collections import defaultdict

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agentwell import config
from agentwell.adapters import detect_adapter, BaseAdapter
from agentwell.monitor.drift import DriftState, analyze as drift_analyze
from agentwell.monitor.quality import QualityState, analyze as quality_analyze
from agentwell.monitor.coordination import analyze as coord_analyze
from agentwell.storage.db import init_db, create_session, record_health_event
from agentwell.guard import (
    sanitize_messages, validate_output, safe_parse_json,
    InputViolation, OutputViolation, install_redactor,
)

# Install log redactor before any logging occurs (OWASP LLM02 / A09)
install_redactor()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
log = logging.getLogger("agentwell")

# Warn on startup if no API key set (OWASP A05 — security misconfiguration)
if not config.API_KEY:
    log.warning("AGENTWELL_API_KEY not set — proxy is open to anyone on this network. Set it for production use.")

# ---------------------------------------------------------------------------
# Rate limiting (OWASP LLM10 — unbounded consumption)
# Simple in-memory sliding window: max 60 req/min per IP
# ---------------------------------------------------------------------------
_RATE_WINDOW = 60       # seconds
_RATE_MAX = 60          # requests per window
_rate_store: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> bool:
    now = time.monotonic()
    window = _rate_store[ip]
    # Drop entries older than window
    _rate_store[ip] = [t for t in window if now - t < _RATE_WINDOW]
    if len(_rate_store[ip]) >= _RATE_MAX:
        return False
    _rate_store[ip].append(now)
    return True


# Global session state (in-memory, per process)
_drift_state = DriftState()
_quality_state = QualityState()
_session_id: str = ""
_adapter: BaseAdapter | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _session_id, _adapter
    await init_db()
    _adapter = await detect_adapter(config.UPSTREAM_URL)
    _session_id = await create_session(config.UPSTREAM_URL, _adapter.name)
    log.info(f"agentwell started | upstream={config.UPSTREAM_URL} adapter={_adapter.name} session={_session_id}")
    yield


app = FastAPI(title="agentwell", lifespan=lifespan)

# CORS — locked to localhost only unless explicitly configured (OWASP A05)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _auth_ok(request: Request) -> bool:
    if not config.API_KEY:
        return True
    provided = (
        request.headers.get("authorization", "").removeprefix("Bearer ").strip()
        or request.headers.get("x-api-key", "").strip()
    )
    if not provided:
        return False
    return secrets.compare_digest(provided.encode(), config.API_KEY.encode())


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    return forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "unknown")


def _compute_health(drift_score: int, quality_score: int, coordination_detected: bool) -> int:
    base = int(drift_score * 0.4 + (100 - quality_score) * 0.4 + int(coordination_detected) * 20)
    return max(0, min(100, 100 - base))


@app.get("/health")
async def health():
    upstream_ok = await _adapter.is_healthy() if _adapter else False
    return {
        "status": "ok",
        "upstream": config.UPSTREAM_URL,
        "upstream_healthy": upstream_ok,
        "adapter": _adapter.name if _adapter else "none",
        "session_id": _session_id,
    }


@app.get("/metrics")
async def metrics():
    from agentwell.storage.db import get_session_events
    events = await get_session_events(_session_id)
    if not events:
        return {"session_id": _session_id, "events": 0}
    latest = events[-1]
    return {
        "session_id": _session_id,
        "events": len(events),
        "latest_health_score": latest["health_score"],
        "latest_drift_score": latest["drift_score"],
        "latest_quality_score": latest["quality_score"],
        "coordination_detected": bool(latest["coordination_detected"]),
        "repetition_ratio": latest["repetition_ratio"],
    }


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    # Auth check
    if not _auth_ok(request):
        raise HTTPException(status_code=401, detail="Unauthorized.")

    # Rate limit (OWASP LLM10)
    ip = _client_ip(request)
    if not _check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Max 60 requests/minute.")

    body_bytes = await request.body()

    # Safe JSON parse — never crash on malformed input (OWASP LLM05)
    body = safe_parse_json(body_bytes.decode("utf-8", errors="replace"), context="request_body")
    if not body:
        raise HTTPException(status_code=400, detail="Invalid JSON.")

    messages: list[dict] = body.get("messages", [])
    model: str = body.get("model", "unknown")
    stream: bool = body.get("stream", False)

    # Sanitize inbound messages — block injection attempts (OWASP LLM01)
    try:
        messages = sanitize_messages(messages)
    except InputViolation as e:
        log.warning(f"guard: injection blocked from {ip}: {e}")
        raise HTTPException(status_code=400, detail="Input validation failed.")

    # Coordination check on sanitized messages
    coord_result = coord_analyze(messages)

    # Build prompt text for drift analysis — content in-memory only, never persisted
    prompt_text = " ".join(
        m.get("content", "") if isinstance(m.get("content"), str) else ""
        for m in messages
    )

    # Forward to upstream
    upstream_headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in ("host", "content-length")
    }
    if _adapter:
        upstream_headers.update(_adapter.extra_request_headers())

    start_ms = time.monotonic()

    if stream:
        return await _handle_streaming(
            body_bytes, upstream_headers, model, prompt_text,
            coord_result, start_ms,
        )

    async with httpx.AsyncClient(timeout=120) as client:
        try:
            upstream_resp = await client.post(
                _adapter.chat_url(),
                content=body_bytes,
                headers=upstream_headers,
            )
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Upstream unreachable: {e}")

    response_ms = int((time.monotonic() - start_ms) * 1000)
    had_error = upstream_resp.status_code >= 400

    # Safe parse response (OWASP LLM05)
    resp_body = safe_parse_json(upstream_resp.text, context="upstream_response")

    token_in = resp_body.get("usage", {}).get("prompt_tokens", 0)
    token_out = resp_body.get("usage", {}).get("completion_tokens", 0)
    finish_reason = ""
    response_text = ""
    if resp_body.get("choices"):
        finish_reason = resp_body["choices"][0].get("finish_reason", "")
        response_text = resp_body["choices"][0].get("message", {}).get("content", "") or ""

    # Scan response for secrets before any logging (OWASP LLM02)
    try:
        validate_output(response_text, context="upstream_response")
    except OutputViolation:
        log.error("guard: secret pattern in upstream response — health event still recorded, content not logged")
        response_text = "[REDACTED — secret pattern detected]"

    drift_result = drift_analyze(prompt_text, response_text, _drift_state)
    quality_result = quality_analyze(token_out, response_ms, finish_reason, had_error, _quality_state)

    all_flags = quality_result.flags + coord_result.signals
    health_score = _compute_health(drift_result.drift_score, quality_result.quality_score, coord_result.coordination_detected)

    asyncio.create_task(record_health_event(
        session_id=_session_id,
        health_score=health_score,
        drift_score=drift_result.drift_score,
        quality_score=quality_result.quality_score,
        coordination_detected=coord_result.coordination_detected,
        repetition_ratio=drift_result.repetition_ratio,
        flags=all_flags,
        token_in=token_in,
        token_out=token_out,
        response_ms=response_ms,
        model=model,
    ))

    if health_score < config.HEALTH_THRESHOLD:
        log.warning(f"Health alert | score={health_score} drift={drift_result.drift_score} quality={quality_result.quality_score} flags={all_flags}")

    response_headers = dict(upstream_resp.headers)
    response_headers["X-Agentwell-Health"] = str(health_score)
    response_headers["X-Agentwell-Flags"] = ",".join(all_flags) if all_flags else "none"
    response_headers["X-Agentwell-Privacy"] = "metadata-only"
    response_headers.pop("content-encoding", None)
    response_headers.pop("transfer-encoding", None)

    return Response(
        content=upstream_resp.content,
        status_code=upstream_resp.status_code,
        headers=response_headers,
        media_type="application/json",
    )


async def _handle_streaming(
    body_bytes: bytes,
    upstream_headers: dict,
    model: str,
    prompt_text: str,
    coord_result,
    start_ms: float,
):
    async def stream_generator():
        token_out = 0
        response_text_parts: list[str] = []
        finish_reason = ""

        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST",
                _adapter.chat_url(),
                content=body_bytes,
                headers=upstream_headers,
            ) as upstream:
                async for line in upstream.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            chunk = safe_parse_json(line[6:], context="stream_chunk")
                            delta = chunk.get("choices", [{}])[0].get("delta", {})
                            content_piece = delta.get("content", "")
                            if content_piece:
                                response_text_parts.append(content_piece)
                                token_out += 1
                            fr = chunk.get("choices", [{}])[0].get("finish_reason")
                            if fr:
                                finish_reason = fr
                        except Exception:
                            pass
                    yield (line + "\n\n").encode()

        response_ms = int((time.monotonic() - start_ms) * 1000)
        response_text = "".join(response_text_parts)

        # Scan stream response for secrets (OWASP LLM02)
        try:
            validate_output(response_text, context="stream_response")
        except OutputViolation:
            response_text = "[REDACTED]"

        drift_result = drift_analyze(prompt_text, response_text, _drift_state)
        quality_result = quality_analyze(token_out, response_ms, finish_reason, False, _quality_state)
        all_flags = quality_result.flags + coord_result.signals
        health_score = _compute_health(drift_result.drift_score, quality_result.quality_score, coord_result.coordination_detected)

        asyncio.create_task(record_health_event(
            session_id=_session_id,
            health_score=health_score,
            drift_score=drift_result.drift_score,
            quality_score=quality_result.quality_score,
            coordination_detected=coord_result.coordination_detected,
            repetition_ratio=drift_result.repetition_ratio,
            flags=all_flags,
            token_in=0,
            token_out=token_out,
            response_ms=response_ms,
            model=model,
        ))

        if health_score < config.HEALTH_THRESHOLD:
            log.warning(f"Health alert (stream) | score={health_score} flags={all_flags}")

    return StreamingResponse(stream_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("agentwell.proxy.server:app", host="0.0.0.0", port=config.PORT, reload=False)

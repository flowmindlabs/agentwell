from __future__ import annotations
import time
import json
import secrets
import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import StreamingResponse

from agentwell import config
from agentwell.adapters import detect_adapter, BaseAdapter
from agentwell.monitor.drift import DriftState, analyze as drift_analyze
from agentwell.monitor.quality import QualityState, analyze as quality_analyze
from agentwell.monitor.coordination import analyze as coord_analyze
from agentwell.storage.db import init_db, create_session, record_health_event

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("agentwell")

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
    if not _auth_ok(request):
        raise HTTPException(status_code=401, detail="Unauthorized.")

    body_bytes = await request.body()
    try:
        body = json.loads(body_bytes)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON.")

    messages: list[dict] = body.get("messages", [])
    model: str = body.get("model", "unknown")
    stream: bool = body.get("stream", False)

    # Coordination check — scans message structure only, no content stored
    coord_result = coord_analyze(messages)

    # Build prompt text for drift analysis (content used in-memory only, never persisted)
    prompt_text = " ".join(
        m.get("content", "") if isinstance(m.get("content"), str) else ""
        for m in messages
    )

    # Forward request to upstream
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
            coord_result, start_ms, messages,
        )

    async with httpx.AsyncClient(timeout=config._get_int("REQUEST_TIMEOUT_MS", 120000) / 1000) as client:
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

    try:
        resp_body = upstream_resp.json()
    except Exception:
        resp_body = {}

    token_in = resp_body.get("usage", {}).get("prompt_tokens", 0)
    token_out = resp_body.get("usage", {}).get("completion_tokens", 0)
    finish_reason = ""
    response_text = ""
    if resp_body.get("choices"):
        finish_reason = resp_body["choices"][0].get("finish_reason", "")
        response_text = resp_body["choices"][0].get("message", {}).get("content", "") or ""

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
    messages: list[dict],
):
    """Pass streaming responses through transparently. Monitor metadata only."""

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
                            chunk = json.loads(line[6:])
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

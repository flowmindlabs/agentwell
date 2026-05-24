from __future__ import annotations
import httpx


class BaseAdapter:
    name: str = "base"

    def __init__(self, upstream_url: str) -> None:
        self.upstream_url = upstream_url.rstrip("/")

    async def is_healthy(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.upstream_url}/health")
                return resp.status_code == 200
        except Exception:
            return False

    def chat_url(self) -> str:
        return f"{self.upstream_url}/v1/chat/completions"


async def detect_adapter(upstream_url: str) -> BaseAdapter:
    """Auto-detect upstream type from /health response. Falls back to openai_compat."""
    from agentwell.adapters.ai_proxy import AiProxyAdapter
    from agentwell.adapters.litellm import LiteLLMAdapter
    from agentwell.adapters.openai_compat import OpenAICompatAdapter

    url = upstream_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{url}/health")
            if resp.status_code == 200:
                # ai-proxy fingerprint: health response has no extra keys beyond status+timestamp
                # but response headers may have X-Proxy-* — check body shape
                body = resp.json()
                if "status" in body and "providers" not in body and "litellm" not in str(resp.headers).lower():
                    # Could be ai-proxy — verify by checking for X-Proxy-Provider on a dummy path
                    # Use conservative detection: ai-proxy /health returns exactly {status, timestamp}
                    if set(body.keys()) <= {"status", "timestamp"}:
                        return AiProxyAdapter(url)

                if "x-litellm-version" in resp.headers or "litellm" in body.get("version", "").lower():
                    return LiteLLMAdapter(url)
    except Exception:
        pass

    return OpenAICompatAdapter(url)

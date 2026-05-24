from agentwell.adapters import BaseAdapter


class AiProxyAdapter(BaseAdapter):
    """Deep integration adapter for flowmindlabs/ai-proxy.

    Fingerprint: GET /health returns exactly {status, timestamp}.
    Default port: 3030. Supports X-Proxy-Provider, X-Cache, X-Proxy-Fallback headers.
    """
    name = "ai_proxy"

    def extra_request_headers(self) -> dict:
        return {"X-Agentwell-Source": "agentwell"}

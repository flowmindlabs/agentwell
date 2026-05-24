from agentwell.adapters import BaseAdapter


class LiteLLMAdapter(BaseAdapter):
    """Adapter for LiteLLM upstream proxy.

    Fingerprint: x-litellm-version present in /health response headers,
    or 'litellm' present in health body version field.
    """
    name = "litellm"

    def extra_request_headers(self) -> dict:
        return {"X-Agentwell-Source": "agentwell"}

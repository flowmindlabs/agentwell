from agentwell.adapters import BaseAdapter


class OpenAICompatAdapter(BaseAdapter):
    """Generic adapter for any OpenAI-compatible upstream endpoint.

    Works with any proxy that speaks the OpenAI /v1/chat/completions format.
    The developer sets AGENTWELL_UPSTREAM to their endpoint — agentwell does
    not know or need to know what is behind that URL.
    """
    name = "openai_compat"

    def extra_request_headers(self) -> dict:
        return {"X-Agentwell-Source": "agentwell"}

import os
from dotenv import load_dotenv

# System env vars always win — .env only fills gaps (local dev fallback)
load_dotenv(override=False)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def _get_int(key: str, default: int) -> int:
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default


def _get_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, str(default)).lower()
    return val in ("1", "true", "yes")


UPSTREAM_URL: str = _get("AGENTWELL_UPSTREAM", "http://localhost:3030")
PORT: int = _get_int("AGENTWELL_PORT", 3001)
API_KEY: str = _get("AGENTWELL_API_KEY", "")
GROQ_API_KEY: str = _get("GROQ_API_KEY", "")
HEALTH_THRESHOLD: int = _get_int("AGENTWELL_HEALTH_THRESHOLD", 70)
WINDOW_SIZE: int = _get_int("AGENTWELL_WINDOW_SIZE", 20)
DB_PATH: str = _get("AGENTWELL_DB_PATH", "./agentwell.db")
STORE_EMBEDDINGS: bool = _get_bool("AGENTWELL_STORE_EMBEDDINGS", False)

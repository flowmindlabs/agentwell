import time
import uuid
import urllib.parse
import aiosqlite
from agentwell.config import DB_PATH


CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    started_at  REAL NOT NULL,
    upstream_url TEXT NOT NULL,
    adapter_type TEXT NOT NULL
)
"""

CREATE_HEALTH_EVENTS = """
CREATE TABLE IF NOT EXISTS health_events (
    id                    TEXT PRIMARY KEY,
    session_id            TEXT NOT NULL,
    timestamp             REAL NOT NULL,
    health_score          INTEGER NOT NULL,
    drift_score           INTEGER NOT NULL,
    quality_score         INTEGER NOT NULL,
    coordination_detected INTEGER NOT NULL,
    repetition_ratio      REAL NOT NULL,
    flags                 TEXT NOT NULL,
    token_in              INTEGER NOT NULL,
    token_out             INTEGER NOT NULL,
    response_ms           INTEGER NOT NULL,
    model                 TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
)
"""

# Raw prompt/response text columns are intentionally absent from this schema.
# agentwell stores metadata only — content privacy is enforced at the DB layer.


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(CREATE_SESSIONS)
        await db.execute(CREATE_HEALTH_EVENTS)
        await db.commit()


async def create_session(upstream_url: str, adapter_type: str) -> str:
    # Strip query params — they may contain embedded API keys
    parsed = urllib.parse.urlparse(upstream_url)
    safe_url = parsed._replace(query="", fragment="").geturl()
    session_id = str(uuid.uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?)",
            (session_id, time.time(), safe_url, adapter_type),
        )
        await db.commit()
    return session_id


async def record_health_event(
    session_id: str,
    health_score: int,
    drift_score: int,
    quality_score: int,
    coordination_detected: bool,
    repetition_ratio: float,
    flags: list[str],
    token_in: int,
    token_out: int,
    response_ms: int,
    model: str,
) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO health_events VALUES
               (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                session_id,
                time.time(),
                health_score,
                drift_score,
                quality_score,
                int(coordination_detected),
                repetition_ratio,
                ",".join(flags),
                token_in,
                token_out,
                response_ms,
                model,
            ),
        )
        await db.commit()


async def get_session_events(session_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM health_events WHERE session_id = ? ORDER BY timestamp ASC",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_recent_events(limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM health_events ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
    return [dict(r) for r in rows]

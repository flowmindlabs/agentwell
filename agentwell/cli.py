"""
agentwell CLI — command line interface for agentwell.

Commands:
    agentwell start             start the proxy server
    agentwell status            show live health from running proxy
    agentwell report            print today's health report from DB
    agentwell init              scaffold .env in current directory
"""

from __future__ import annotations
import argparse
import asyncio
import json
import os
import sys
from pathlib import Path


# ── helpers ─────────────────────────────────────────────────────────────────

def _green(s: str) -> str:  return f"\033[92m{s}\033[0m"
def _amber(s: str) -> str:  return f"\033[93m{s}\033[0m"
def _red(s: str) -> str:    return f"\033[91m{s}\033[0m"
def _muted(s: str) -> str:  return f"\033[90m{s}\033[0m"
def _bold(s: str) -> str:   return f"\033[1m{s}\033[0m"

def _health_color(score: int) -> str:
    if score >= 80: return _green(str(score))
    if score >= 60: return _amber(str(score))
    if score >= 40: return _amber(str(score))
    return _red(str(score))

def _health_label(score: int) -> str:
    if score >= 80: return _green("healthy")
    if score >= 60: return _amber("watch")
    if score >= 40: return _amber("warning")
    return _red("critical")


# ── start ────────────────────────────────────────────────────────────────────

def cmd_start(args: argparse.Namespace) -> None:
    """Start the agentwell proxy server."""
    import uvicorn
    from agentwell import config

    port = args.port or config.PORT
    host = args.host or "0.0.0.0"

    print(_bold("agentwell") + f"  proxy starting on {host}:{port}")
    print(_muted(f"  upstream : {config.UPSTREAM_URL}"))
    print(_muted(f"  db       : {config.DB_PATH}"))
    print(_muted(f"  threshold: {config.HEALTH_THRESHOLD}"))
    print()

    from agentwell.proxy.server import app
    uvicorn.run(app, host=host, port=port, log_level="warning")


# ── status ───────────────────────────────────────────────────────────────────

async def _fetch_status(base_url: str) -> None:
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{base_url}/health", timeout=5)
            data = r.json()
            print(_bold("agentwell") + "  proxy status")
            print()
            status = data.get("status", "unknown")
            color = _green if status == "ok" else _red
            print(f"  status    : {color(status)}")
            print(f"  upstream  : {data.get('upstream', '—')}")
            uh = data.get("upstream_healthy", False)
            print(f"  upstream  : {'reachable' if uh else _muted('no /health endpoint (normal for Groq)')}")
            print(f"  adapter   : {data.get('adapter', '—')}")
            print(f"  session   : {_muted(data.get('session_id', '—'))}")
        except httpx.ConnectError:
            print(_red("error") + f"  proxy not reachable at {base_url}")
            print(_muted("  start with: agentwell start"))
            sys.exit(1)

    try:
        r = await client.get(f"{base_url}/metrics", timeout=5)
        if r.status_code == 200:
            m = r.json()
            print()
            print("  " + _bold("session metrics"))
            health = m.get("health_score")
            if health is not None:
                print(f"  health    : {_health_color(health)}  {_health_label(health)}")
            calls = m.get("total_calls")
            if calls is not None:
                print(f"  calls     : {calls}")
            flags = m.get("flags")
            if flags:
                print(f"  flags     : {_amber(flags)}")
    except Exception:
        pass


def cmd_status(args: argparse.Namespace) -> None:
    """Show live health from running proxy."""
    base_url = args.proxy or os.environ.get("AGENTWELL_PROXY_URL", "http://localhost:3001")
    asyncio.run(_fetch_status(base_url))


# ── report ───────────────────────────────────────────────────────────────────

async def _fetch_report(date_str: str) -> None:
    import aiosqlite
    from agentwell import config

    async with aiosqlite.connect(config.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT id FROM sessions WHERE started_at LIKE ?", (f"{date_str}%",)
        ) as cur:
            sessions = [row["id"] async for row in cur]

        if not sessions:
            print(_muted(f"no data for {date_str}"))
            return

        events = []
        for sid in sessions:
            async with db.execute(
                "SELECT * FROM health_events WHERE session_id = ? ORDER BY timestamp ASC", (sid,)
            ) as cur:
                async for row in cur:
                    events.append(dict(row))

    if not events:
        print(_muted(f"no events for {date_str}"))
        return

    scores = [e["health_score"] for e in events]
    drift  = [e["drift_score"] for e in events]
    qual   = [e["quality_score"] for e in events]
    coord  = sum(1 for e in events if e.get("coordination_detected"))

    print(_bold("agentwell") + f"  daily report  {_muted(date_str)}")
    print()
    print(f"  events    : {len(events)}  sessions: {len(sessions)}")
    print(f"  health    : {_health_color(scores[0])} → {_health_color(scores[-1])}"
          f"  {_muted(f'min={min(scores)} avg={round(sum(scores)/len(scores),1)}')}")
    print(f"  drift     : {drift[0]} → {drift[-1]}  {_muted(f'max={max(drift)}')}")
    print(f"  quality   : {qual[0]} → {qual[-1]}  {_muted(f'min={min(qual)}')}")

    if coord:
        print(f"  coord     : {_amber(str(coord))} coordination events detected")
    else:
        print(f"  coord     : {_green('none')}")

    # threshold crossings
    below80 = next((i+1 for i, e in enumerate(events) if e["health_score"] < 80), None)
    below60 = next((i+1 for i, e in enumerate(events) if e["health_score"] < 60), None)
    below40 = next((i+1 for i, e in enumerate(events) if e["health_score"] < 40), None)
    if below80:
        print()
        print(f"  {_muted('thresholds crossed:')}")
        print(f"    < 80 at event {below80}")
        if below60: print(f"    < 60 at event {below60}")
        if below40: print(f"    {_red(f'< 40 at event {below40}  ← critical')}")


def cmd_report(args: argparse.Namespace) -> None:
    """Print health report from DB."""
    import datetime
    date_str = args.date or datetime.date.today().isoformat()
    asyncio.run(_fetch_report(date_str))


# ── init ─────────────────────────────────────────────────────────────────────

_ENV_TEMPLATE = """\
AGENTWELL_UPSTREAM=https://api.groq.com/openai
AGENTWELL_PORT=3001
AGENTWELL_HEALTH_THRESHOLD=70
AGENTWELL_WINDOW_SIZE=20
AGENTWELL_DB_PATH=./agentwell.db
AGENTWELL_STORE_EMBEDDINGS=false
AGENTWELL_API_KEY=
GROQ_API_KEY=your-groq-key-here
"""

def cmd_init(args: argparse.Namespace) -> None:
    """Scaffold .env in current directory."""
    env_path = Path(".env")
    if env_path.exists() and not args.force:
        print(_amber("warning") + "  .env already exists. use --force to overwrite.")
        return
    env_path.write_text(_ENV_TEMPLATE)
    print(_green("created") + "  .env")
    print(_muted("  edit GROQ_API_KEY before starting the proxy"))
    print(_muted("  never commit .env — it is already in .gitignore"))


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="agentwell",
        description="behavioral health monitoring for AI agents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
commands:
  start     start the proxy server
  status    show live health from running proxy
  report    print today's health report from DB
  init      scaffold .env in current directory
        """,
    )
    parser.add_argument("--version", action="version", version="agentwell 0.1.3")
    sub = parser.add_subparsers(dest="command")

    # start
    p_start = sub.add_parser("start", help="start the proxy server")
    p_start.add_argument("--host", default=None, help="bind host (default: 0.0.0.0)")
    p_start.add_argument("--port", type=int, default=None, help="bind port (default: from .env or 3001)")

    # status
    p_status = sub.add_parser("status", help="show live health from running proxy")
    p_status.add_argument("--proxy", default=None, help="proxy URL (default: http://localhost:3001)")

    # report
    p_report = sub.add_parser("report", help="print health report from DB")
    p_report.add_argument("--date", default=None, help="date YYYY-MM-DD (default: today)")

    # init
    p_init = sub.add_parser("init", help="scaffold .env in current directory")
    p_init.add_argument("--force", action="store_true", help="overwrite existing .env")

    args = parser.parse_args()

    if args.command == "start":
        cmd_start(args)
    elif args.command == "status":
        cmd_status(args)
    elif args.command == "report":
        cmd_report(args)
    elif args.command == "init":
        cmd_init(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

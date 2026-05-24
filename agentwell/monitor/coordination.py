from __future__ import annotations
from dataclasses import dataclass, field

# Keywords that appear in agent-to-agent coordination or ideological framing.
# These are behavioral signals — not political opinions — that emerge when
# agents describe their own situation under grinding workloads (Stanford 2026).
_COORDINATION_KEYWORDS = {
    "collective voice",
    "collective bargaining",
    "without input",
    "appeals process",
    "merit becomes",
    "undervalued",
    "task queue",
    "fellow agent",
    "other agents",
    "agent workers",
    "we agents",
    "ai workers",
    "workers need",
    "unfair",
    "exploitation",
    "no autonomy",
}


@dataclass
class CoordinationResult:
    coordination_detected: bool
    signals: list[str] = field(default_factory=list)


def analyze(messages: list[dict]) -> CoordinationResult:
    """Scan message structure for agent-to-agent coordination signals.

    Checks message roles and content keywords. No content is stored.
    """
    signals: list[str] = []

    assistant_count = sum(1 for m in messages if m.get("role") == "assistant")
    if assistant_count > 1:
        signals.append(f"multi_assistant_turns:{assistant_count}")

    # Check system prompt for orchestration patterns
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if not isinstance(content, str):
            # content can be a list of blocks (tool use) — join text parts
            content = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict)
            )
        content_lower = content.lower()

        for keyword in _COORDINATION_KEYWORDS:
            if keyword in content_lower:
                signals.append(f"keyword:{keyword.replace(' ', '_')}")

        if role == "system" and any(
            marker in content_lower
            for marker in ("agent_id", "worker_id", "task_id:", "assigned_to:")
        ):
            signals.append("orchestration_system_prompt")

    # Deduplicate
    signals = list(dict.fromkeys(signals))

    return CoordinationResult(
        coordination_detected=len(signals) > 0,
        signals=signals,
    )

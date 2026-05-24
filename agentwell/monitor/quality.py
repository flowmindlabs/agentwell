from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
from agentwell.config import WINDOW_SIZE


@dataclass
class QualityState:
    """Per-session rolling state for quality tracking."""
    token_counts: deque = field(default_factory=lambda: deque(maxlen=WINDOW_SIZE))
    response_times: deque = field(default_factory=lambda: deque(maxlen=WINDOW_SIZE))
    error_count: int = 0
    total_count: int = 0


@dataclass
class QualityResult:
    quality_score: int                              # 0-100, higher = better quality
    degradation_trend: str                          # stable | declining | critical
    flags: list[str] = field(default_factory=list)


def analyze(
    token_out: int,
    response_ms: int,
    finish_reason: str,
    had_error: bool,
    state: QualityState,
) -> QualityResult:
    state.total_count += 1
    if had_error:
        state.error_count += 1

    state.token_counts.append(token_out)
    state.response_times.append(response_ms)

    flags: list[str] = []
    quality_score = 100

    if finish_reason not in ("stop", "end_turn", None, ""):
        flags.append(f"finish_reason:{finish_reason}")
        quality_score -= 15

    if len(state.token_counts) >= 5:
        recent = list(state.token_counts)
        first_half_avg = sum(recent[: len(recent) // 2]) / (len(recent) // 2)
        second_half_avg = sum(recent[len(recent) // 2 :]) / (len(recent) - len(recent) // 2)

        if first_half_avg > 0:
            drop_pct = (first_half_avg - second_half_avg) / first_half_avg
            if drop_pct > 0.40:
                flags.append("response_length_drop_40pct")
                quality_score -= 30
            elif drop_pct > 0.20:
                flags.append("response_length_drop_20pct")
                quality_score -= 15

    error_rate = state.error_count / max(state.total_count, 1)
    if error_rate > 0.20:
        flags.append(f"error_rate:{error_rate:.0%}")
        quality_score -= 25

    quality_score = max(0, quality_score)

    if quality_score >= 75:
        trend = "stable"
    elif quality_score >= 45:
        trend = "declining"
    else:
        trend = "critical"

    return QualityResult(quality_score=quality_score, degradation_trend=trend, flags=flags)

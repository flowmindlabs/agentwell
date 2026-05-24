"""
agentwell/guard/log_redactor.py

Strips secret patterns from log lines before they reach any handler.
Covers: GitHub PAT, GitLab PAT, Slack tokens, AWS keys, Bearer tokens,
OpenAI keys, Anthropic keys, generic api_key= patterns.

OWASP LLM02 — Sensitive Information Disclosure
OWASP A09   — Security Logging Failures

Usage:
    from agentwell.guard.log_redactor import install_redactor
    install_redactor()  # call once at startup, before any logging

After install, all log records pass through redact() automatically.
"""
from __future__ import annotations
import re
import logging

_REDACT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"ghp_[A-Za-z0-9]{36}"), "ghp_***REDACTED***"),
    (re.compile(r"glpat-[A-Za-z0-9\-_]{20,}"), "glpat-***REDACTED***"),
    (re.compile(r"xox[bpoa]-[A-Za-z0-9\-]+"), "xox-***REDACTED***"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AKIA***REDACTED***"),
    (re.compile(r"sk-[A-Za-z0-9]{32,}"), "sk-***REDACTED***"),
    (re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]{20,}", re.IGNORECASE), r"\1***REDACTED***"),
    (re.compile(r"hooks\.slack\.com/services/[A-Za-z0-9/]+"), "hooks.slack.com/***REDACTED***"),
    (re.compile(r"(api[_\s]?key|x-api-key|apikey)\s*[=:]\s*\S{8,}", re.IGNORECASE), r"\1=***REDACTED***"),
    (re.compile(r"(password|secret|token)\s*[=:]\s*\S{8,}", re.IGNORECASE), r"\1=***REDACTED***"),
]


def redact(text: str) -> str:
    for pattern, replacement in _REDACT_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class _RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(redact(str(a)) for a in record.args)
        return True


def install_redactor() -> None:
    """Install redacting filter on the root logger. Call once at startup."""
    root = logging.getLogger()
    for handler in root.handlers:
        handler.addFilter(_RedactingFilter())
    # Also add to root logger itself for early-stage records
    root.addFilter(_RedactingFilter())

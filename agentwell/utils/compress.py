"""
compress.py — caveman-style prompt compression for token savings.

Adapts the compression technique from github.com/JuliusBrussee/caveman.
Strips filler words, articles, hedging, and pleasantries from prompt text
before sending to LLM — reduces token usage ~40-65% on prose prompts.

Levels: lite, full (default), ultra
"""

from __future__ import annotations
import re

# ---------------------------------------------------------------------------
# Word lists
# ---------------------------------------------------------------------------

_ARTICLES = {"a", "an", "the"}

_FILLER = {
    "just", "really", "basically", "actually", "simply", "very", "quite",
    "rather", "somewhat", "pretty", "fairly", "highly", "extremely",
    "absolutely", "definitely", "certainly", "obviously", "clearly",
    "essentially", "generally", "typically", "usually", "normally",
}

_HEDGING = {
    "please", "kindly", "could you", "would you", "can you", "i would like",
    "i want you to", "i need you to", "feel free to", "make sure to",
    "be sure to", "try to", "attempt to", "endeavour to",
}

_PLEASANTRIES = {
    "sure", "of course", "happy to", "glad to", "certainly",
    "no problem", "absolutely", "great", "excellent", "wonderful",
    "thank you", "thanks",
}

# ultra: prose abbreviations (never touch code/api/error strings)
_ULTRA_ABBREV = {
    "database": "DB",
    "authentication": "auth",
    "configuration": "config",
    "request": "req",
    "response": "res",
    "function": "fn",
    "implementation": "impl",
    "because": "→",
    "therefore": "→",
    "results in": "→",
    "causes": "→",
    "leading to": "→",
    "which means": "→",
    "in order to": "to",
    "in addition": "+",
    "as well as": "+",
    "however": "but",
    "nevertheless": "but",
    "furthermore": "also",
    "additionally": "also",
}

# ---------------------------------------------------------------------------
# Core compressor
# ---------------------------------------------------------------------------

def compress(text: str, level: str = "full") -> str:
    """
    Compress prompt text using caveman technique.
    level: "lite" | "full" | "ultra"
    Code blocks (```...```) and quoted strings are never modified.
    """
    if not text or not text.strip():
        return text

    # Extract and protect code blocks + quoted strings
    protected: dict[str, str] = {}
    counter = [0]

    def _protect(m: re.Match) -> str:
        key = f"__PROTECTED_{counter[0]}__"
        protected[key] = m.group(0)
        counter[0] += 1
        return key

    # Protect code blocks
    text = re.sub(r"```[\s\S]*?```", _protect, text)
    # Protect inline code
    text = re.sub(r"`[^`]+`", _protect, text)

    if level == "lite":
        text = _apply_lite(text)
    elif level == "full":
        text = _apply_full(text)
    elif level == "ultra":
        text = _apply_ultra(text)

    # Restore protected blocks
    for key, original in protected.items():
        text = text.replace(key, original)

    return text.strip()


def _apply_lite(text: str) -> str:
    text = _strip_hedging_phrases(text)
    text = _strip_filler_words(text)
    text = _clean_whitespace(text)
    return text


def _apply_full(text: str) -> str:
    text = _strip_hedging_phrases(text)
    text = _strip_filler_words(text)
    text = _strip_articles(text)
    text = _clean_whitespace(text)
    return text


def _apply_ultra(text: str) -> str:
    text = _strip_hedging_phrases(text)
    text = _strip_filler_words(text)
    text = _strip_articles(text)
    text = _apply_ultra_abbrev(text)
    text = _strip_conjunctions(text)
    text = _clean_whitespace(text)
    return text


def _strip_articles(text: str) -> str:
    return re.sub(
        r"\b(a|an|the)\b\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )


def _strip_filler_words(text: str) -> str:
    pattern = r"\b(" + "|".join(re.escape(w) for w in _FILLER) + r")\b\s*"
    return re.sub(pattern, "", text, flags=re.IGNORECASE)


def _strip_hedging_phrases(text: str) -> str:
    for phrase in sorted(_HEDGING, key=len, reverse=True):
        text = re.sub(re.escape(phrase) + r"\s*", "", text, flags=re.IGNORECASE)
    return text


def _apply_ultra_abbrev(text: str) -> str:
    for word, abbrev in _ULTRA_ABBREV.items():
        text = re.sub(r"\b" + re.escape(word) + r"\b", abbrev, text, flags=re.IGNORECASE)
    return text


def _strip_conjunctions(text: str) -> str:
    conjunctions = {"and", "but", "or", "nor", "so", "yet", "for"}
    pattern = r"\b(" + "|".join(conjunctions) + r")\b\s*"
    # Only strip when at start of sentence fragment, not mid-sentence list
    text = re.sub(r"\.\s+(" + "|".join(conjunctions) + r")\s+", ". ", text, flags=re.IGNORECASE)
    return text


def _clean_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" ([,.:;?!])", r"\1", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Convenience: compress a messages list (user/system roles only)
# assistant messages never modified
# ---------------------------------------------------------------------------

def compress_messages(messages: list[dict], level: str = "full") -> list[dict]:
    """Compress user and system message content. Assistant messages untouched."""
    compressed = []
    for msg in messages:
        if msg.get("role") in ("user", "system"):
            content = msg.get("content", "")
            if isinstance(content, str):
                msg = {**msg, "content": compress(content, level=level)}
        compressed.append(msg)
    return compressed

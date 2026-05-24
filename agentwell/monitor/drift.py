from __future__ import annotations
from dataclasses import dataclass, field
from collections import deque
import numpy as np
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from sentence_transformers import SentenceTransformer
from agentwell.config import WINDOW_SIZE

_model: SentenceTransformer | None = None
_analyzer = SentimentIntensityAnalyzer()


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        # Tiny model — 22MB, runs fully local, no API cost
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


@dataclass
class DriftState:
    """Per-session rolling state for drift detection. Holds embeddings and sentiment scores."""
    embeddings: deque = field(default_factory=lambda: deque(maxlen=WINDOW_SIZE))
    sentiment_scores: deque = field(default_factory=lambda: deque(maxlen=WINDOW_SIZE))


@dataclass
class DriftResult:
    drift_score: int        # 0-100, higher = more drift or more grinding
    repetition_ratio: float # 0.0-1.0, fraction of window that is highly similar
    sentiment_delta: float  # shift in compound sentiment vs session baseline


def analyze(prompt_text: str, response_text: str, state: DriftState) -> DriftResult:
    """Compute drift metrics from prompt + response metadata. No text is stored."""
    model = _get_model()

    prompt_embedding = model.encode(prompt_text, normalize_embeddings=True)
    response_sentiment = _analyzer.polarity_scores(response_text)["compound"]

    repetition_ratio = 0.0
    drift_score = 50

    if len(state.embeddings) > 0:
        embeddings_arr = np.array(list(state.embeddings))
        similarities = embeddings_arr @ prompt_embedding
        repetition_ratio = float(np.mean(similarities > 0.90))

        # High repetition = grinding (score goes up = bad)
        # High variance in similarity = ideological drift (also bad)
        similarity_variance = float(np.var(similarities))
        drift_score = min(100, int(repetition_ratio * 60 + similarity_variance * 800))

    sentiment_delta = 0.0
    if len(state.sentiment_scores) > 0:
        baseline = float(np.mean(list(state.sentiment_scores)))
        sentiment_delta = response_sentiment - baseline

    # Embeddings computed and used — not persisted to disk (config.STORE_EMBEDDINGS controls that)
    state.embeddings.append(prompt_embedding)
    state.sentiment_scores.append(response_sentiment)

    return DriftResult(
        drift_score=drift_score,
        repetition_ratio=repetition_ratio,
        sentiment_delta=sentiment_delta,
    )

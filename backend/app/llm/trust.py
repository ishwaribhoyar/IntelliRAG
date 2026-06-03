"""Trust layer — DATA-DRIVEN confidence calibration.
Bucket-based accuracy tracking + calibration curve.
"""
import logging

logger = logging.getLogger(__name__)

# Track for consistency check
_last_confidence: dict[str, float] = {}

# Data-driven calibration buckets (persisted in memory for session)
_calibration_buckets = {
    "high": {"count": 0, "correct": 0},
    "medium": {"count": 0, "correct": 0},
    "low": {"count": 0, "correct": 0},
}
_calibration_factor: float = 1.0


def normalize(score: float, max_score: float) -> float:
    """Normalize score to 0–1 range."""
    if max_score <= 0:
        return 0.0
    return min(max(score / max_score, 0.0), 1.0)


def _get_bucket(conf: float) -> str:
    if conf > 0.8:
        return "high"
    elif conf > 0.5:
        return "medium"
    return "low"


def _bucket_accuracy(bucket: str) -> float:
    data = _calibration_buckets[bucket]
    return data["correct"] / max(data["count"], 1)


def update_calibration(confidence_score: float, was_correct: bool):
    """Update calibration data with a new observation."""
    global _calibration_factor
    bucket = _get_bucket(confidence_score)
    _calibration_buckets[bucket]["count"] += 1
    if was_correct:
        _calibration_buckets[bucket]["correct"] += 1

    # Auto-adjust if high confidence accuracy drops below 0.7
    high_acc = _bucket_accuracy("high")
    if _calibration_buckets["high"]["count"] >= 3 and high_acc < 0.7:
        _calibration_factor = 0.85
    else:
        _calibration_factor = 1.0


def compute_confidence(
    retrieval_scores: list[float],
    reranker_score: float = 0.0,
    llm_confidence: str = "medium",
    num_chunks: int = 0,
) -> dict:
    """Compute DATA-DRIVEN calibrated confidence.

    Formula: base = 0.5 * retrieval + 0.3 * reranker + 0.2 * llm
    Then:    score = base * calibration_factor

    Returns: {level, score, reason, components}
    """
    if not retrieval_scores:
        return _build_result(0.05, "No relevant content found", {})

    top_score = max(retrieval_scores)
    avg_score = sum(retrieval_scores) / len(retrieval_scores)

    max_retrieval = 0.1
    retrieval_norm = normalize(top_score, max_retrieval)
    if num_chunks >= 3 and avg_score > 0.03:
        retrieval_norm = min(retrieval_norm + 0.1, 1.0)

    reranker_norm = normalize(reranker_score, 10.0) if reranker_score > 0 else 0.5

    llm_conf_map = {"high": 0.9, "medium": 0.6, "low": 0.3}
    llm_norm = llm_conf_map.get(llm_confidence, 0.5)

    # Weighted combination + calibration
    base_score = 0.5 * retrieval_norm + 0.3 * reranker_norm + 0.2 * llm_norm
    score = round(max(0.0, min(1.0, base_score * _calibration_factor)), 3)

    components = {
        "retrieval": round(retrieval_norm, 3),
        "reranker": round(reranker_norm, 3),
        "llm": round(llm_norm, 3),
        "top_retrieval_raw": round(top_score, 5),
        "num_chunks": num_chunks,
        "calibration_factor": _calibration_factor,
    }

    reason = (
        f"retrieval={retrieval_norm:.2f}, reranker={reranker_norm:.2f}, "
        f"llm={llm_norm:.2f}, cal={_calibration_factor} | sources={num_chunks}"
    )

    _consistency_check(score)
    logger.info(f"[CONFIDENCE] {_get_level(score)} ({score}) — {reason}")

    return _build_result(score, reason, components)


def _build_result(score: float, reason: str, components: dict) -> dict:
    return {"level": _get_level(score), "score": score, "reason": reason, "components": components}


def _get_level(score: float) -> str:
    if score >= 0.7:
        return "high"
    elif score >= 0.4:
        return "medium"
    return "low"


def _consistency_check(score: float):
    """Warn if confidence swings > 0.4."""
    key = "global"
    if key in _last_confidence:
        delta = abs(score - _last_confidence[key])
        if delta > 0.4:
            logger.warning(f"[TRUST WARNING] Unstable: {_last_confidence[key]:.3f} → {score:.3f} (Δ={delta:.3f})")
    _last_confidence[key] = score


def validate_confidence(predictions: list[dict]) -> dict:
    """Validate calibration: accuracy per confidence bucket.

    Input: list of {confidence: float, correct: bool}
    Output: accuracy at high/medium/low bands + calibration status.
    """
    if not predictions:
        return {"error": "No predictions to validate"}

    buckets = {"high": [0, 0], "medium": [0, 0], "low": [0, 0]}  # [correct, total]

    for p in predictions:
        conf = p.get("confidence", 0.5)
        correct = p.get("correct", False)
        bucket = _get_bucket(conf)
        buckets[bucket][1] += 1
        if correct:
            buckets[bucket][0] += 1

    high_acc = buckets["high"][0] / max(buckets["high"][1], 1)
    med_acc = buckets["medium"][0] / max(buckets["medium"][1], 1)
    low_acc = buckets["low"][0] / max(buckets["low"][1], 1)

    # Update global calibration
    global _calibration_factor
    if buckets["high"][1] >= 3 and high_acc < 0.7:
        _calibration_factor = 0.85
        logger.warning(f"[CALIBRATION] High-conf accuracy {high_acc:.1%} < 70%. Factor → 0.85")
    else:
        _calibration_factor = 1.0

    result = {
        "confidence_accuracy": {
            "high": round(high_acc, 4),
            "medium": round(med_acc, 4),
            "low": round(low_acc, 4),
        },
        "sample_counts": {
            "high": buckets["high"][1],
            "medium": buckets["medium"][1],
            "low": buckets["low"][1],
        },
        "calibration_factor": _calibration_factor,
        "well_calibrated": high_acc >= 0.7,
    }

    logger.info(
        f"\nConfidence Calibration:\n"
        f"  High Accuracy:   {high_acc:.1%} ({buckets['high'][1]} samples)\n"
        f"  Medium Accuracy: {med_acc:.1%} ({buckets['medium'][1]} samples)\n"
        f"  Low Accuracy:    {low_acc:.1%} ({buckets['low'][1]} samples)\n"
        f"  Calibration factor: {_calibration_factor}"
    )

    return result


def get_calibration_factor() -> float:
    return _calibration_factor


def build_source_citations(chunks: list[dict]) -> list[dict]:
    return [{"chunk_id": c.get("chunk_id", ""), "section": c.get("section", ""),
             "page": c.get("page", 1), "preview": c.get("text", "")[:150]} for c in chunks]


def should_fallback(confidence: dict) -> bool:
    return confidence["score"] < 0.5


FALLBACK_RESPONSE = (
    "The information requested could not be reliably found in the uploaded document. "
    "Please try rephrasing your question or ensure the relevant content is in the document."
)

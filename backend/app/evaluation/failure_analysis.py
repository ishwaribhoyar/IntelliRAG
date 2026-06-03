"""Failure analysis — SEMANTIC correctness check (not string overlap).
Uses the same MiniLM embedder for cosine similarity.
"""
import logging
import numpy as np
from app.rag.embedder import embed_single

logger = logging.getLogger(__name__)


def semantic_similarity(text_a: str, text_b: str) -> float:
    """Compute cosine similarity between two texts using MiniLM embeddings."""
    if not text_a or not text_b:
        return 0.0
    try:
        emb_a = np.array(embed_single(text_a))
        emb_b = np.array(embed_single(text_b))
        dot = np.dot(emb_a, emb_b)
        norm = np.linalg.norm(emb_a) * np.linalg.norm(emb_b)
        if norm == 0:
            return 0.0
        return float(dot / norm)
    except Exception as e:
        logger.warning(f"Semantic similarity failed: {e}")
        return 0.0


def analyze_failures(evaluation_details: list[dict]) -> dict:
    """Categorize failures using SEMANTIC similarity (not word overlap).

    Failure types:
    1. retrieval_failure — no relevant chunks found
    2. generation_failure — chunks found but answer semantically wrong (sim < 0.65)
    3. confidence_mismatch — low confidence but answer was correct (sim >= 0.65)

    Returns failure breakdown with percentages and similarity scores.
    """
    total = len(evaluation_details)
    if total == 0:
        return {"error": "No evaluation details provided"}

    retrieval_failures = 0
    generation_failures = 0
    confidence_mismatches = 0
    successes = 0
    failure_cases = []
    similarity_scores = []

    for detail in evaluation_details:
        answer = detail.get("answer", "")
        expected = detail.get("expected", "")
        q_type = detail.get("type", "")
        chunks_found = detail.get("chunks_found", len(detail.get("hybrid_top3", [])))
        confidence = detail.get("confidence", {})
        conf_score = confidence.get("score", 0.5) if isinstance(confidence, dict) else 0.5

        # Skip missing-type — handled by not-found accuracy
        if q_type == "missing":
            continue

        # 1. Retrieval failure: no chunks found
        if chunks_found == 0 or "not enough context" in answer.lower():
            retrieval_failures += 1
            failure_cases.append({
                "type": "retrieval_failure",
                "question": detail.get("question", "")[:100],
                "reason": "No relevant chunks retrieved",
                "similarity": 0.0,
            })
            continue

        # 2. Semantic correctness check (not word overlap)
        if expected and expected.lower() != "not_in_document":
            sim = semantic_similarity(answer, expected)
            similarity_scores.append(sim)
            correct = sim >= 0.65

            if not correct:
                generation_failures += 1
                failure_cases.append({
                    "type": "generation_failure",
                    "question": detail.get("question", "")[:100],
                    "reason": f"Semantic similarity {sim:.2f} < 0.65 threshold",
                    "similarity": round(sim, 3),
                })
                continue

            # 3. Confidence mismatch: correct answer but low confidence
            if conf_score < 0.5:
                confidence_mismatches += 1
                failure_cases.append({
                    "type": "confidence_mismatch",
                    "question": detail.get("question", "")[:100],
                    "reason": f"Correct (sim={sim:.2f}) but confidence={conf_score:.2f}",
                    "similarity": round(sim, 3),
                })
                continue

            successes += 1
        else:
            successes += 1

    avg_sim = round(sum(similarity_scores) / max(len(similarity_scores), 1), 3)

    report = {
        "total_evaluated": total,
        "successes": successes,
        "success_rate": round(successes / max(total, 1) * 100, 1),
        "avg_semantic_similarity": avg_sim,
        "failure_breakdown": {
            "retrieval_failures": retrieval_failures,
            "retrieval_failure_pct": round(retrieval_failures / max(total, 1) * 100, 1),
            "generation_failures": generation_failures,
            "generation_failure_pct": round(generation_failures / max(total, 1) * 100, 1),
            "confidence_mismatches": confidence_mismatches,
            "confidence_mismatch_pct": round(confidence_mismatches / max(total, 1) * 100, 1),
        },
        "failure_cases": failure_cases[:10],
    }

    logger.info(
        f"\nFailure Breakdown (semantic):\n"
        f"  Total: {total} | Successes: {successes} ({report['success_rate']}%)\n"
        f"  Avg semantic similarity: {avg_sim}\n"
        f"  Retrieval failures: {retrieval_failures} ({report['failure_breakdown']['retrieval_failure_pct']}%)\n"
        f"  Generation failures: {generation_failures} ({report['failure_breakdown']['generation_failure_pct']}%)\n"
        f"  Confidence mismatches: {confidence_mismatches} ({report['failure_breakdown']['confidence_mismatch_pct']}%)"
    )

    return report

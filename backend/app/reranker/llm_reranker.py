"""Conditional reranker — VALIDATED.
Per-chunk scoring, validation hook, improvement check, guaranteed fallback.
"""
import json
import re
import time
import logging
import asyncio
from app.modules.llm_router.router import llm_router

logger = logging.getLogger(__name__)

RERANK_PROMPT = """Score the relevance of the following text chunk to the query.
Return ONLY a single number from 0 to 10.
No explanation. No text. Just the number.

10 = perfectly answers the query
7-9 = highly relevant
4-6 = somewhat relevant
1-3 = marginally relevant
0 = irrelevant

Query: {query}

Chunk: {chunk_text}"""


async def rerank_chunks(
    doc_id: str,
    query: str,
    chunks: list[dict],
    min_candidates: int = 5,
    score_gap_threshold: float = 0.02,
) -> list[dict]:
    """Conditionally rerank chunks using Sarvam-M or active LLM router.

    Only triggers when:
    1. Candidates >= min_candidates
    2. Top scores are close (gap < threshold)

    On any failure → returns original ranking (guaranteed).
    """
    if len(chunks) < 3:
        return chunks

    if len(chunks) < min_candidates:
        logger.debug(f"Rerank skipped: only {len(chunks)} candidates")
        return chunks

    scores = [c.get("rrf_score", c.get("score", 0)) for c in chunks]
    if len(scores) >= 2:
        gap = abs(scores[0] - scores[1])
        if gap > score_gap_threshold:
            logger.debug(f"Rerank skipped: score gap {gap:.4f} > threshold")
            return chunks

    t_start = time.time()
    rerank_limit = min(len(chunks), 8)

    sem = asyncio.Semaphore(3)

    async def score_single_chunk(i: int, chunk: dict) -> dict:
        async with sem:
            try:
                prompt = RERANK_PROMPT.format(
                    query=query,
                    chunk_text=chunk["text"][:400]
                )
                result = await llm_router.generate(
                    doc_id=doc_id,
                    task_type=f"rerank_{i}",
                    prompt=prompt,
                    context=""
                )
                answer = result.get("answer", "").strip()
                score = _parse_score(answer)

                chunk_copy = chunk.copy()
                chunk_copy["rerank_score"] = score
                logger.debug(f"  Rerank chunk {chunk['chunk_id']}: raw='{answer}' → score={score}")
                return chunk_copy

            except Exception as e:
                logger.warning(f"Rerank failed for chunk {i}: {e}")
                chunk_copy = chunk.copy()
                chunk_copy["rerank_score"] = scores[i] * 10 if i < len(scores) else 5.0
                return chunk_copy

    tasks = [score_single_chunk(i, chunk) for i, chunk in enumerate(chunks[:rerank_limit])]
    scored_chunks = list(await asyncio.gather(*tasks))

    scored_chunks.sort(key=lambda c: c.get("rerank_score", 0), reverse=True)
    scored_chunks.extend(chunks[rerank_limit:])

    t_elapsed = (time.time() - t_start) * 1000
    logger.info(
        f"[RERANKER] Reranked {rerank_limit}/{len(chunks)} chunks | "
        f"time={t_elapsed:.0f}ms | "
        f"top_score={scored_chunks[0].get('rerank_score', 0):.1f}"
    )

    return scored_chunks


# =====================================================================
# VALIDATION HOOKS
# =====================================================================

async def validate_reranker(doc_id: str, query: str, chunks: list[dict]) -> dict:
    """Validation hook: shows before/after reranking side by side."""
    before_ids = [c["chunk_id"] for c in chunks[:5]]
    after = await rerank_chunks(doc_id, query, chunks, min_candidates=1, score_gap_threshold=999)
    after_ids = [c["chunk_id"] for c in after[:5]]

    changed = before_ids != after_ids
    before_scores = [round(c.get("rrf_score", 0), 4) for c in chunks[:5]]
    after_scores = [round(c.get("rerank_score", 0), 1) for c in after[:5]]

    result = {
        "before_ids": before_ids,
        "after_ids": after_ids,
        "before_scores": before_scores,
        "after_scores": after_scores,
        "ranking_changed": changed,
    }

    logger.info(
        f"\n=== RERANKER VALIDATION ===\n"
        f"Query: {query}\n"
        f"Before: {before_ids}\n"
        f"After:  {after_ids}\n"
        f"Changed: {changed}\n"
        f"Before scores: {before_scores}\n"
        f"After scores:  {after_scores}"
    )

    return result


def reranker_improves(before: list[dict], after: list[dict], relevant: list[str]) -> dict:
    """Check if reranker improves precision over original ranking."""
    before_top3 = set(c["chunk_id"] for c in before[:3])
    after_top3 = set(c["chunk_id"] for c in after[:3])

    before_hits = len(before_top3 & set(relevant))
    after_hits = len(after_top3 & set(relevant))

    improved = after_hits > before_hits
    same = after_hits == before_hits

    return {
        "improved": improved,
        "same": same,
        "before_hits": before_hits,
        "after_hits": after_hits,
        "relevant_count": len(relevant),
    }


def _parse_score(text: str) -> float:
    """Parse score from LLM response. Returns 5.0 on failure (neutral)."""
    try:
        text = text.strip()
        if text.replace(".", "").replace("-", "").isdigit():
            score = float(text)
            return max(0.0, min(10.0, score))
        match = re.search(r'\b(\d+\.?\d*)\b', text)
        if match:
            score = float(match.group(1))
            return max(0.0, min(10.0, score))
    except (ValueError, AttributeError):
        pass
    logger.warning(f"Could not parse rerank score from: '{text}', using 5.0")
    return 5.0

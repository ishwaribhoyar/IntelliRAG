"""Retriever — weighted multi-query, deduplication, token-safe truncation."""
import logging
import numpy as np
from app.rag.embedder import embed_single
from app.rag.vector_store import search_index
from app.config import MAX_CONTEXT_TOKENS

logger = logging.getLogger(__name__)


def estimate_tokens(text: str) -> int:
    """Conservative token estimation."""
    return int(len(text.split()) * 1.5)


def sanitize_query(query: str) -> str | None:
    """Sanitize user query. Returns None if invalid."""
    if not query:
        return None
    query = query.strip()
    if len(query) > 300:
        query = query[:300]
    if not query:
        return None
    # Remove repetitive tokens
    words = query.split()
    seen = []
    for w in words:
        if w.lower() not in [s.lower() for s in seen[-3:]] if seen else True:
            seen.append(w)
    return " ".join(seen)


def expand_queries(query: str) -> list[tuple[str, float]]:
    """Generate weighted query variations."""
    return [
        (query, 0.6),
        (f"Explain {query}", 0.2),
        (f"Key points of {query}", 0.2),
    ]


async def retrieve_chunks(
    doc_id: str,
    query: str,
    top_k: int = 3,
) -> list[dict]:
    """Full retrieval pipeline: multi-query → merge → dedup → sort → truncate.

    Args:
        doc_id: Document to search
        query: User query
        top_k: Number of chunks to retrieve (varies by feature)
    """
    clean_query = sanitize_query(query)
    if not clean_query:
        return []

    weighted_queries = expand_queries(clean_query)
    all_results: dict[str, dict] = {}

    for q_text, weight in weighted_queries:
        q_embedding = embed_single(q_text)
        results = await search_index(doc_id, q_embedding, top_k=top_k + 2)

        for chunk in results:
            cid = chunk["chunk_id"]
            weighted_score = chunk["score"] * weight
            if cid in all_results:
                all_results[cid]["score"] += weighted_score
            else:
                chunk_copy = chunk.copy()
                chunk_copy["score"] = weighted_score
                all_results[cid] = chunk_copy

    # Sort by combined relevance score (descending)
    sorted_chunks = sorted(all_results.values(), key=lambda x: x["score"], reverse=True)

    # Token-safe truncation
    final_chunks = []
    total_tokens = 0
    for chunk in sorted_chunks:
        chunk_tokens = estimate_tokens(chunk["text"])
        if total_tokens + chunk_tokens > MAX_CONTEXT_TOKENS:
            break
        final_chunks.append(chunk)
        total_tokens += chunk_tokens

    logger.info(
        f"Retrieved {len(final_chunks)} chunks for doc={doc_id}, "
        f"tokens={total_tokens}/{MAX_CONTEXT_TOKENS}"
    )
    return final_chunks


def get_top_k_for_task(task_type: str) -> int:
    """Dynamic top-k based on task type."""
    mapping = {
        "ask": 3,
        "quiz": 5,
        "flashcards": 5,
        "summary": 7,
        "slides": 5,
        "mock_test": 8,
        "fun_facts": 3,
        "mentor": 3,
    }
    return mapping.get(task_type, 3)

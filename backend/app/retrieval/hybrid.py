"""Hybrid retrieval with Reciprocal Rank Fusion (RRF) — VALIDATED.
Debug output, comparison mode, latency tracking.
"""
import time
import logging
from app.rag.embedder import embed_single
from app.indexing.vector_index import search_vector
from app.indexing.bm25_index import load_bm25_index
from app.state import bm25_indexes, chunk_store
from app.query.expander import expand_query
from app.query.router import route_query

logger = logging.getLogger(__name__)


async def hybrid_retrieve(
    doc_id: str,
    query: str,
    query_type: str = "factual",
    top_k: int = 7,
    vector_weight: float = 0.5,
    bm25_weight: float = 0.5,
    rrf_k: int = 10,
) -> list[dict]:
    """Full hybrid retrieval pipeline with debug output.

    1. Multi-query expansion
    2. Vector search per variant
    3. BM25 search per variant
    4. RRF fusion
    5. Deduplicate + sort

    Returns ranked list of chunk dicts with 'rrf_score' field.
    """
    t_start = time.time()

    # Expand queries
    variants = expand_query(query, query_type)

    # Collect results from all sources
    vector_results: dict[str, dict] = {}  # chunk_id → chunk with score
    bm25_results: dict[str, float] = {}   # chunk_id → best score

    # --- Vector search ---
    t_vector = time.time()
    for q_text, weight in variants:
        q_embedding = embed_single(q_text)
        results = await search_vector(doc_id, q_embedding, top_k=top_k + 3)
        for chunk in results:
            cid = chunk["chunk_id"]
            weighted_score = chunk["score"] * weight
            if cid in vector_results:
                existing = vector_results[cid]["score"]
                if weighted_score > existing:
                    vector_results[cid] = chunk.copy()
                    vector_results[cid]["score"] = weighted_score
                else:
                    vector_results[cid]["score"] += weighted_score * 0.3
            else:
                c = chunk.copy()
                c["score"] = weighted_score
                vector_results[cid] = c
    t_vector_done = time.time()

    # --- BM25 search ---
    t_bm25 = time.time()
    if doc_id not in bm25_indexes:
        bm25 = load_bm25_index(doc_id)
        if bm25:
            bm25_indexes[doc_id] = bm25

    if doc_id in bm25_indexes:
        bm25_idx = bm25_indexes[doc_id]
        for q_text, weight in variants:
            results = bm25_idx.search(q_text, top_k=top_k + 3)
            for cid, score in results:
                weighted = score * weight
                if cid in bm25_results:
                    bm25_results[cid] = max(bm25_results[cid], weighted)
                else:
                    bm25_results[cid] = weighted
    t_bm25_done = time.time()

    # --- DEBUG: Top results from each source ---
    vector_top3 = sorted(vector_results.items(), key=lambda x: x[1]["score"], reverse=True)[:3]
    bm25_top3 = sorted(bm25_results.items(), key=lambda x: x[1], reverse=True)[:3]

    logger.info(
        f"\n[RETRIEVAL DEBUG] query='{query[:60]}'\n"
        f"  Vector top 3: {[(cid, round(c['score'], 4)) for cid, c in vector_top3]}\n"
        f"  BM25 top 3:   {[(cid, round(s, 4)) for cid, s in bm25_top3]}\n"
        f"  Vector time:  {(t_vector_done - t_vector)*1000:.1f}ms\n"
        f"  BM25 time:    {(t_bm25_done - t_bm25)*1000:.1f}ms"
    )

    # --- RRF Fusion ---
    vector_ranked = sorted(vector_results.items(), key=lambda x: x[1]["score"], reverse=True)
    vector_rank_map = {cid: rank + 1 for rank, (cid, _) in enumerate(vector_ranked)}

    bm25_ranked = sorted(bm25_results.items(), key=lambda x: x[1], reverse=True)
    bm25_rank_map = {cid: rank + 1 for rank, (cid, _) in enumerate(bm25_ranked)}

    all_chunk_ids = set(vector_rank_map.keys()) | set(bm25_rank_map.keys())
    rrf_scores: dict[str, float] = {}

    for cid in all_chunk_ids:
        score = 0.0
        if cid in vector_rank_map:
            score += vector_weight * (1.0 / (rrf_k + vector_rank_map[cid]))
        if cid in bm25_rank_map:
            score += bm25_weight * (1.0 / (rrf_k + bm25_rank_map[cid]))
        rrf_scores[cid] = score

    sorted_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)

    # Build result list
    chunks = chunk_store.get(doc_id, [])
    chunk_map = {c["chunk_id"]: c for c in chunks}

    results = []
    for cid in sorted_ids[:top_k]:
        chunk = None
        if cid in vector_results:
            chunk = vector_results[cid].copy()
        elif cid in chunk_map:
            chunk = chunk_map[cid].copy()
        if chunk:
            chunk["rrf_score"] = rrf_scores[cid]
            chunk["vector_rank"] = vector_rank_map.get(cid)
            chunk["bm25_rank"] = bm25_rank_map.get(cid)
            results.append(chunk)

    t_total = (time.time() - t_start) * 1000
    logger.info(
        f"[RETRIEVAL RESULT] {len(vector_results)} vector + {len(bm25_results)} bm25 "
        f"-> {len(results)} RRF-fused | total={t_total:.1f}ms"
    )

    # DEBUG: RRF top 3
    for i, r in enumerate(results[:3]):
        logger.info(
            f"  RRF #{i+1}: {r['chunk_id']} | rrf={r['rrf_score']:.4f} | "
            f"v_rank={r.get('vector_rank')} | bm25_rank={r.get('bm25_rank')} | "
            f"section={r.get('section','')[:30]}"
        )

    return results


def get_chunks_by_ordered_ids(doc_id: str, chunk_ids: list[str]) -> list[dict]:
    """Restore chunks in the same order as ``chunk_ids`` (fixed context for refresh)."""
    if not chunk_ids:
        return []
    all_chunks = chunk_store.get(doc_id) or []
    cmap = {c.get("chunk_id"): c for c in all_chunks if c.get("chunk_id")}
    out: list[dict] = []
    for cid in chunk_ids:
        ch = cmap.get(cid)
        if ch is not None:
            out.append(ch.copy())
    return out


# =====================================================================
# COMPARISON MODE — for validation
# =====================================================================

async def compare_retrieval(doc_id: str, query: str, top_k: int = 5) -> dict:
    """Compare vector-only vs hybrid retrieval.
    Returns side-by-side results for ablation testing.
    """
    # Vector-only
    q_embedding = embed_single(query)
    vector_only = await search_vector(doc_id, q_embedding, top_k=top_k)

    # Hybrid (RRF)
    hybrid = await hybrid_retrieve(doc_id, query, top_k=top_k)

    # Format results
    vector_top = [
        {"chunk_id": c["chunk_id"], "score": round(c["score"], 4),
         "section": c.get("section", ""), "preview": c["text"][:100]}
        for c in vector_only
    ]
    hybrid_top = [
        {"chunk_id": c["chunk_id"], "rrf_score": round(c["rrf_score"], 4),
         "vector_rank": c.get("vector_rank"), "bm25_rank": c.get("bm25_rank"),
         "section": c.get("section", ""), "preview": c["text"][:100]}
        for c in hybrid
    ]

    # Overlap analysis
    vector_ids = set(c["chunk_id"] for c in vector_only)
    hybrid_ids = set(c["chunk_id"] for c in hybrid)
    overlap = vector_ids & hybrid_ids
    bm25_unique = hybrid_ids - vector_ids  # chunks that BM25 contributed

    comparison = {
        "query": query,
        "vector_top": vector_top,
        "hybrid_top": hybrid_top,
        "overlap_count": len(overlap),
        "bm25_unique_contributions": len(bm25_unique),
        "bm25_contributed_ids": list(bm25_unique),
    }

    logger.info(
        f"[COMPARISON] vector={len(vector_top)} hybrid={len(hybrid_top)} "
        f"overlap={len(overlap)} bm25_unique={len(bm25_unique)}"
    )

    return comparison


# =====================================================================
# HIGH-LEVEL ENTRY POINT
# =====================================================================

async def retrieve_for_task(doc_id: str, query: str, task_type: str = "ask") -> list[dict]:
    """High-level retrieval entry point with query routing."""
    strategy = route_query(query)

    task_k_overrides = {
        "ask": 5, "quiz": 7, "flashcards": 7, "summary": 10,
        "slides": 7, "mock_test": 10, "fun_facts": 5, "mentor": 5,
        "search": strategy["top_k"],
    }
    top_k = task_k_overrides.get(task_type, strategy["top_k"])

    chunks = await hybrid_retrieve(
        doc_id=doc_id,
        query=query,
        query_type=strategy["query_type"],
        top_k=top_k,
        vector_weight=strategy["vector_weight"],
        bm25_weight=strategy["bm25_weight"],
        rrf_k=strategy["rrf_k"],
    )

    return chunks

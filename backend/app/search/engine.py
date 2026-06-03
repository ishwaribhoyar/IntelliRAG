"""Search engine mode — keyword, hybrid, and AI search modes."""
import logging
from app.retrieval.hybrid import hybrid_retrieve, retrieve_for_task
from app.retrieval.mmr import mmr_filter
from app.retrieval.context_filter import filter_context
from app.reranker.llm_reranker import rerank_chunks
from app.query.router import route_query
from app.rag.llm_client import call_llm
from app.llm.trust import compute_confidence, build_source_citations, should_fallback, FALLBACK_RESPONSE
from app.indexing.bm25_index import load_bm25_index
from app.state import bm25_indexes, chunk_store
from app.search.spell import suggest_query

logger = logging.getLogger(__name__)


async def search(
    doc_id: str,
    query: str,
    mode: str = "auto",
    user_id: str = "default",
    llm_variant: str | None = None,
) -> dict:
    """Search engine with 3 modes.

    Modes:
        'keyword' — BM25 only, returns ranked chunks (no LLM)
        'hybrid'  — RRF fusion, returns ranked chunks (no LLM)
        'ai'      — Full pipeline: hybrid + reranker + LLM answer
        'auto'    — Auto-detect: short query → keyword; long → ai

    Returns:
        {mode, results, answer?, confidence?, sources?, query_info}
    """
    # Typo correction
    spell_result = suggest_query(query, doc_id)
    effective_query = spell_result["corrected"] if spell_result["did_you_mean"] else query

    # Auto-detect mode
    if mode == "auto":
        word_count = len(effective_query.split())
        if word_count <= 3:
            mode = "keyword"
        elif word_count <= 8:
            mode = "hybrid"
        else:
            mode = "ai"

    strategy = route_query(effective_query)

    # --- KEYWORD MODE ---
    if mode == "keyword":
        if doc_id not in bm25_indexes:
            bm25 = load_bm25_index(doc_id)
            if bm25:
                bm25_indexes[doc_id] = bm25

        if doc_id not in bm25_indexes:
            return {"mode": "keyword", "results": [], "error": "No BM25 index found"}

        bm25_results = bm25_indexes[doc_id].search(effective_query, top_k=10)

        # Map to chunk data
        chunks = chunk_store.get(doc_id, [])
        chunk_map = {c["chunk_id"]: c for c in chunks}
        results = []
        for cid, score in bm25_results:
            if cid in chunk_map:
                c = chunk_map[cid].copy()
                c["score"] = score
                results.append(c)

        return {
            "mode": "keyword",
            "results": [_chunk_to_result(c) for c in results],
            "query_info": strategy,
            **({"did_you_mean": spell_result["corrected"], "original_query": spell_result["original"]} if spell_result["did_you_mean"] else {}),
        }

    # --- HYBRID MODE ---
    if mode == "hybrid":
        chunks = await hybrid_retrieve(
            doc_id, query,
            query_type=strategy["query_type"],
            top_k=strategy["top_k"],
            vector_weight=strategy["vector_weight"],
            bm25_weight=strategy["bm25_weight"],
            rrf_k=strategy["rrf_k"],
        )
        chunks = mmr_filter(chunks, max_chunks=10)

        return {
            "mode": "hybrid",
            "results": [_chunk_to_result(c) for c in chunks],
            "query_info": strategy,
            **({"did_you_mean": spell_result["corrected"], "original_query": spell_result["original"]} if spell_result["did_you_mean"] else {}),
        }

    # --- AI MODE (full pipeline) ---
    # 1. Hybrid retrieval
    chunks = await hybrid_retrieve(
        doc_id, query,
        query_type=strategy["query_type"],
        top_k=strategy["top_k"],
        vector_weight=strategy["vector_weight"],
        bm25_weight=strategy["bm25_weight"],
        rrf_k=strategy["rrf_k"],
    )

    # 2. Conditional reranking
    if strategy["needs_rerank"]:
        chunks = await rerank_chunks(doc_id, query, chunks)

    # 3. MMR diversity
    chunks = mmr_filter(chunks, max_chunks=7)

    # 4. Context filtering
    chunks = filter_context(chunks, max_tokens=1500)

    # 5. Confidence check
    scores = [c.get("rrf_score", c.get("score", 0)) for c in chunks]
    confidence = compute_confidence(scores, num_chunks=len(chunks))

    if should_fallback(confidence):
        return {
            "mode": "ai",
            "answer": FALLBACK_RESPONSE,
            "confidence": confidence,
            "sources": [],
            "results": [_chunk_to_result(c) for c in chunks],
            "query_info": strategy,
        }

    # 6. LLM answer
    context = "\n\n".join(c["text"] for c in chunks)
    from app.generators.prompts import get_prompt
    prompt = get_prompt("ask")
    result = await call_llm(
        doc_id, "search_ai", prompt, f"{context}\n\nQuestion: {query}", llm_variant=llm_variant
    )

    sources = build_source_citations(chunks)

    return {
        "mode": "ai",
        "answer": result.get("answer", ""),
        "confidence": confidence,
        "sources": sources,
        "results": [_chunk_to_result(c) for c in chunks],
        "cached": result.get("cached", False),
        "query_info": strategy,
        **({"did_you_mean": spell_result["corrected"], "original_query": spell_result["original"]} if spell_result["did_you_mean"] else {}),
    }


def _chunk_to_result(chunk: dict) -> dict:
    """Convert chunk dict to search result format."""
    return {
        "chunk_id": chunk.get("chunk_id", ""),
        "text": chunk.get("text", "")[:300],
        "section": chunk.get("section", ""),
        "page": chunk.get("page", 1),
        "score": round(chunk.get("rrf_score", chunk.get("score", 0)), 4),
        "type": chunk.get("type", "text"),
    }

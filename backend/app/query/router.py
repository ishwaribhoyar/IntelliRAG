"""Query router — decides retrieval strategy based on query characteristics."""
import logging
from app.query.classifier import classify_query, get_query_complexity

logger = logging.getLogger(__name__)


def route_query(query: str) -> dict:
    """Determine retrieval strategy based on query analysis.

    Returns dict with:
        query_type: str          — factual/analytical/procedural/comparison
        complexity: str          — simple/moderate/complex
        vector_weight: float     — weight for vector search in RRF
        bm25_weight: float       — weight for BM25 search in RRF
        top_k: int               — number of chunks to retrieve
        needs_rerank: bool       — whether to apply reranker
        rrf_k: int               — RRF constant (lower = more weight to top results)
    """
    query_type = classify_query(query)
    complexity = get_query_complexity(query)
    word_count = len(query.split())

    # Default balanced weights
    vector_w = 0.5
    bm25_w = 0.5
    top_k = 7
    needs_rerank = False
    rrf_k = 10

    # Short keyword queries → BM25-heavy
    if word_count <= 3:
        bm25_w = 0.7
        vector_w = 0.3
        top_k = 5
        rrf_k = 5

    # Long descriptive queries → Vector-heavy
    elif word_count > 12:
        vector_w = 0.7
        bm25_w = 0.3
        top_k = 10
        rrf_k = 15
        needs_rerank = True

    # Comparison / analytical → need more chunks + reranking
    if query_type in ("comparison", "analytical"):
        top_k = max(top_k, 8)
        needs_rerank = True

    # Procedural → moderate
    elif query_type == "procedural":
        top_k = max(top_k, 7)

    strategy = {
        "query_type": query_type,
        "complexity": complexity,
        "vector_weight": vector_w,
        "bm25_weight": bm25_w,
        "top_k": top_k,
        "needs_rerank": needs_rerank,
        "rrf_k": rrf_k,
    }

    logger.info(
        f"Query routed: type={query_type}, complexity={complexity}, "
        f"v_w={vector_w}, bm25_w={bm25_w}, k={top_k}, rerank={needs_rerank}"
    )
    return strategy

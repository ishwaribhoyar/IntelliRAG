"""
features.search_engine
======================
Top-level feature: Search Engine

Business capability: Multi-modal document search combining keyword, vector,
and hybrid search with spell suggestions, query routing, and smart ranking.

Sub-features mapped to existing modules
-----------------------------------------
keyword_search   → app.search.engine           (BM25-based keyword search)
hybrid_search    → app.retrieval.hybrid        (FAISS + BM25 + RRF fusion)
typo_correction  → app.search.spell            (spell suggestion)
query_routing    → app.query.router            (intent-based routing)
search_ranking   → app.reranker.llm_reranker   (LLM reranking)
indexing         → app.indexing                (BM25 + vector index building)
vector_search    → app.rag                     (dense retrieval)
autocomplete     → app.search.spell            (autocomplete suggestions)
suggestions      → (stub — future)
navigation       → (stub — future)
"""

from app.modules.search_engine.routes import router as search_router     # noqa: F401
from app.modules.search_engine.service import (                           # noqa: F401
    handle_search,
    handle_user_search,
    handle_suggest,
    handle_user_suggest,
    handle_node_chunks,
)
from app.search.engine import search                                       # noqa: F401
from app.search.spell import suggest_query, suggest_autocomplete           # noqa: F401
from app.query.router import route_query                                   # noqa: F401
from app.reranker.llm_reranker import rerank_chunks                       # noqa: F401
from app.indexing.builder import build_indexes                             # noqa: F401

__all__ = [
    "search_router",
    "handle_search",
    "handle_user_search",
    "handle_suggest",
    "handle_user_suggest",
    "handle_node_chunks",
    "search",
    "suggest_query",
    "suggest_autocomplete",
    "route_query",
    "rerank_chunks",
    "build_indexes",
]

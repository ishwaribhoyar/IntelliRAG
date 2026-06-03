"""
features.smart_reranker
=======================
Top-level feature: Smart Reranker

Business capability: Intelligently rerank retrieved documents using LLM-based
scoring, score-gap logic, MMR diversity, and latency-aware fallback.

Sub-features mapped to existing modules
-----------------------------------------
llm_reranking       → app.reranker.llm_reranker   (LLM-based reranking)
mmr                 → app.retrieval.mmr            (Maximal Marginal Relevance)
conditional_rerank  → app.reranker                 (score-gap conditional logic)
score_gap_logic     → app.reranker.llm_reranker    (gap-based triggering)
diversity           → app.retrieval.mmr            (diversity enforcement)
rerank_metrics      → (stub — future telemetry)
latency_control     → (stub — future)
"""

from app.reranker.llm_reranker import rerank_chunks  # noqa: F401
from app.retrieval.mmr import mmr_filter             # noqa: F401

__all__ = [
    "rerank_chunks",
    "mmr_filter",
]

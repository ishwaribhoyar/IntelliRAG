"""
features.grounded_rag
=====================
Top-level feature: Grounded RAG (Retrieval-Augmented Generation)

Business capability: Answer user questions with document-grounded, cited,
hallucination-controlled responses using hybrid retrieval and LLM generation.

Sub-features mapped to existing modules
----------------------------------------
ask_ai               → app.modules.ask_ai          (HTTP routes + handlers)
query_understanding  → app.query                   (classification, expansion, routing)
retrieval            → app.retrieval               (hybrid FAISS+BM25+RRF)
answer_generation    → app.rag, app.generators     (LLM client, generation)
hallucination_control→ app.llm.trust               (trust scoring, fallback)
context_window       → app.rag.user_ask            (context retrieval pipeline)
citations            → (metadata from retrieval results)
confidence           → app.llm.trust               (confidence scoring)
"""

from app.modules.ask_ai.routes import router as ask_router       # noqa: F401
from app.modules.ask_ai.service import handle_ask, handle_mentor # noqa: F401
from app.rag.user_ask import ask_ai, retrieve_context            # noqa: F401
from app.query.classifier import classify_query                  # noqa: F401
from app.query.expander import expand_query                      # noqa: F401
from app.query.router import route_query                         # noqa: F401
from app.retrieval.context_filter import filter_context          # noqa: F401
from app.llm.trust import should_fallback, compute_confidence    # noqa: F401

__all__ = [
    "ask_router",
    "handle_ask",
    "handle_mentor",
    "ask_ai",
    "retrieve_context",
    "classify_query",
    "expand_query",
    "route_query",
    "filter_context",
    "should_fallback",
    "compute_confidence",
]

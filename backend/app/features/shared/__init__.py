"""
features.shared
===============
Top-level: Shared Core Engine Layer

These are the cross-cutting infrastructure engines that multiple features
consume. Features USE shared engines — they do not duplicate them.

Shared engine dependency map
-----------------------------
grounded_rag      → retrieval_core, embedding_core, vector_core
search_engine     → retrieval_core, vector_core, ranking_core
quiz_engine       → retrieval_core
ingestion_pipeline→ embedding_core, vector_core
trust_layer       → (standalone — app.llm.trust)

Sub-engines
-----------
retrieval_core  → app.retrieval        (hybrid FAISS+BM25+RRF + context filter)
embedding_core  → app.rag.embedder     (sentence-transformer embedder)
vector_core     → app.rag.vector_store (FAISS vector store wrapper)
ranking_core    → app.reranker         (reranking logic)
caching         → app.shared.caching   (in-memory cache)
auth            → app.modules.auth     (JWT auth)
database        → app.shared.database  (DB models + session)
logging         → app.core.logging     (structured logging setup)
utils           → app.shared.utils     (document + search utilities)
"""

# retrieval_core
from app.retrieval.context_filter import filter_context   # noqa: F401
from app.retrieval.mmr import mmr_filter                  # noqa: F401

# embedding_core
from app.rag.embedder import embed_texts, warmup          # noqa: F401

# ranking_core
from app.reranker.llm_reranker import rerank_chunks       # noqa: F401

# database
from app.shared.database.session import get_db            # noqa: F401
from app.shared.database.models import Base               # noqa: F401

__all__ = [
    "filter_context", "mmr_filter",
    "embed_texts", "warmup",
    "rerank_chunks",
    "get_db", "Base",
]

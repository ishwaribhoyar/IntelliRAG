"""
features.ingestion_pipeline
============================
Top-level feature: Ingestion Pipeline

Business capability: End-to-end document ingestion — PDF parsing, hierarchical
chunking, embedding, vector/BM25 indexing — with async background queue workers.

Sub-features mapped to existing modules
-----------------------------------------
pdf_parsing      → app.parser                (extractors, normalizer, router)
chunking         → app.chunking              (hierarchical chunker, validator)
indexing         → app.indexing              (vector + BM25 index building)
queue            → app.tasks.pipeline_queue  (async ingestion job queue)
background       → app.tasks.background      (background flush workers)
validation       → app.chunking.validator    (chunk quality validation)
storage          → app.shared.storage        (storage path utilities)
"""

from app.modules.upload_pipeline.routes import router as upload_router      # noqa: F401
from app.modules.upload_pipeline.service import (                            # noqa: F401
    handle_single_upload,
    handle_multi_upload,
    get_doc_status,
    get_user_status,
    retry_failed_doc,
    list_docs_for_user,
    serve_pdf_file,
    delete_document_all,
)
from app.parser.router import route_parser                                   # noqa: F401
from app.chunking.hierarchical import chunk_document                         # noqa: F401
from app.indexing.builder import build_indexes                               # noqa: F401
from app.tasks.pipeline_queue import (                                       # noqa: F401
    start_pipeline_pool,
    stop_pipeline_pool,
    enqueue_pipeline_job,
    queue_stats,
)

__all__ = [
    "upload_router",
    "handle_single_upload",
    "handle_multi_upload",
    "get_doc_status",
    "get_user_status",
    "retry_failed_doc",
    "list_docs_for_user",
    "serve_pdf_file",
    "delete_document_all",
    "route_parser",
    "chunk_document",
    "build_indexes",
    "start_pipeline_pool",
    "stop_pipeline_pool",
    "enqueue_pipeline_job",
    "queue_stats",
]

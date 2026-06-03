"""
features.content_library
=========================
Top-level feature: Content Library

Business capability: Upload, classify, organize, and manage learning documents
with automatic subject/topic detection and hierarchical content structuring.

Sub-features mapped to existing modules
-----------------------------------------
uploads             → app.modules.upload_pipeline     (PDF upload + ingestion)
pdf_management      → app.parser                      (PDF extraction, normalization)
auto_classification → app.core.classifier             (subject/topic classification)
hierarchy_builder   → app.core.unified_hierarchy      (content hierarchy building)
storage             → app.shared.storage              (file path utilities)
metadata            → app.core.library                (catalog and metadata)
deletion            → app.modules.upload_pipeline     (document deletion)
subject_detection   → app.core.classifier             (subject-level detection)
topic_detection     → app.core.classifier             (topic-level detection)
subtopic_mapping    → app.core.unified_hierarchy      (subtopic mapping)
"""

from app.modules.content_library.routes import router as library_router    # noqa: F401
from app.modules.content_library.service import (                           # noqa: F401
    handle_library_add,
    handle_library_list,
    handle_library_hierarchy,
    handle_library_subject,
    handle_library_remove,
    handle_library_reclassify,
)
from app.modules.upload_pipeline.routes import router as upload_router      # noqa: F401
from app.modules.upload_pipeline.service import (                           # noqa: F401
    handle_single_upload,
    handle_multi_upload,
    get_doc_status,
    delete_document_all,
)
from app.core.classifier import classify_document                           # noqa: F401
from app.core.unified_hierarchy import upsert_doc_hierarchy                 # noqa: F401

__all__ = [
    "library_router",
    "handle_library_add",
    "handle_library_list",
    "handle_library_hierarchy",
    "handle_library_subject",
    "handle_library_remove",
    "handle_library_reclassify",
    "upload_router",
    "handle_single_upload",
    "handle_multi_upload",
    "get_doc_status",
    "delete_document_all",
    "classify_document",
    "upsert_doc_hierarchy",
]

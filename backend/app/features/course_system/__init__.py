"""
features.course_system
=======================
Top-level feature: Course System

Business capability: Build, navigate, and track structured learning courses
from document content with automatic hierarchy generation.

Sub-features mapped to existing modules
-----------------------------------------
structure   → app.core.course_structure    (course structure generation)
hierarchy   → app.core.unified_hierarchy   (subject/topic/subtopic tree)
routes      → app.modules.courses.routes   (HTTP routes)
progress    → app.personalization.tracker  (per-course progress tracking)
"""

from app.modules.courses.routes import router as courses_router        # noqa: F401
from app.modules.courses.service import (                              # noqa: F401
    handle_course_structure,
    handle_course_action,
    handle_course_chat,
)
from app.core.course_structure import build_course_structure           # noqa: F401
from app.core.unified_hierarchy import upsert_doc_hierarchy            # noqa: F401

__all__ = [
    "courses_router",
    "handle_course_structure",
    "handle_course_action",
    "handle_course_chat",
    "build_course_structure",
    "upsert_doc_hierarchy",
]

"""
features.analytics
===================
Top-level feature: Analytics

Business capability: Track and expose platform-wide learning analytics
including session metrics, document usage, quiz performance, and engagement.

Sub-features
------------
routes   → app.modules.analytics.routes  (analytics HTTP endpoints)
metrics  → (stub — future metric aggregation)
reports  → (stub — future analytics reporting)
"""

from app.modules.analytics.routes import router as analytics_router  # noqa: F401

__all__ = [
    "analytics_router",
]

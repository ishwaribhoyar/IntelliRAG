"""
features.weakness_detection
============================
Top-level feature: Weakness Detection

Business capability: Track learner performance, detect knowledge gaps, and
provide personalized study guidance based on topic-level analysis.

Sub-features mapped to existing modules
-----------------------------------------
topic_tracking          → app.personalization.tracker   (per-topic result recording)
weak_topic_detection    → app.personalization.tracker   (identifies low-score topics)
recommendation_engine   → app.personalization.advisor   (study recommendations)
learning_patterns       → app.personalization.tracker   (performance trends)
progress_analysis       → app.personalization.tracker   (progress metrics)
study_guidance          → app.personalization.advisor   (personalized advice)
confidence_analysis     → (stub — future)
"""

from app.modules.weaknesses.routes import router as weakness_router      # noqa: F401
from app.modules.weaknesses.service import handle_weakness_dashboard     # noqa: F401
from app.personalization.tracker import (                                 # noqa: F401
    record_topic_result,
    record_quiz_results,
    get_weak_topics,
    get_all_topic_scores,
    get_weak_topics_for_quiz,
)
from app.personalization.advisor import generate_advice, generate_study_plan  # noqa: F401

__all__ = [
    "weakness_router",
    "handle_weakness_dashboard",
    "record_topic_result",
    "record_quiz_results",
    "get_weak_topics",
    "get_all_topic_scores",
    "get_weak_topics_for_quiz",
    "generate_advice",
    "generate_study_plan",
]

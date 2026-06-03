"""
features.trust_layer
====================
Top-level feature: Trust Layer

Business capability: Ensure answer reliability by computing confidence scores,
detecting when the system should fall back, and validating response grounding.

Sub-features mapped to existing modules
-----------------------------------------
confidence           → app.llm.trust   (confidence scoring formula)
hallucination_detection → app.llm.trust (hallucination heuristics)
fallback_logic       → app.llm.trust   (insufficient-context fallback)
answer_validation    → app.llm.trust   (answer quality checks)
uncertainty_detection→ app.llm.trust   (low-confidence detection)
citation_validation  → (stub — future citation cross-check)
grounding_validation → (stub — future grounding validation)
"""

from app.llm.trust import (    # noqa: F401
    should_fallback,
    compute_confidence,
    update_calibration,
)

__all__ = [
    "should_fallback",
    "compute_confidence",
    "update_calibration",
]

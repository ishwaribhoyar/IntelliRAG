"""
features.evaluation_engine
===========================
Top-level feature: Evaluation Engine

Business capability: Measure RAG system performance using recall, MRR,
hallucination rate, and produce failure analysis reports.

Sub-features mapped to existing modules
-----------------------------------------
recall           → app.evaluation.metrics         (Recall@K computation)
mrr              → app.evaluation.metrics         (MRR computation)
hallucination    → app.evaluation.metrics         (hallucination rate)
benchmarks       → app.evaluation.runner          (evaluation runner)
failure_analysis → app.evaluation.failure_analysis (failure case analysis)
reports          → app.evaluation.final_report    (report generation)
latency          → (stub — future latency tracking)
ablation         → (stub — future ablation studies)
logging          → (stub — future eval logging)
metrics_storage  → (stub — future persistent metrics)
"""

from app.modules.evaluation.routes import router as eval_router         # noqa: F401
from app.evaluation.metrics import (                                     # noqa: F401
    recall_at_k,
    mrr,
    accuracy,
    hallucination_rate,
    not_found_accuracy,
)
from app.evaluation.runner import run_evaluation                         # noqa: F401
from app.evaluation.failure_analysis import analyze_failures             # noqa: F401

__all__ = [
    "eval_router",
    "recall_at_k",
    "mrr",
    "accuracy",
    "hallucination_rate",
    "not_found_accuracy",
    "run_evaluation",
    "analyze_failures",
]

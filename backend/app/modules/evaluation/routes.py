"""Evaluation module — routes."""
import logging
from fastapi import APIRouter, HTTPException

from app.shared.utils.doc_utils import _validate_doc_ready

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Evaluation"])


@router.post("/evaluate/{doc_id}")
async def evaluate_document(doc_id: str):
    """Run evaluation pipeline — metrics, ablation, latency."""
    _validate_doc_ready(doc_id)
    from app.evaluation.runner import run_evaluation
    return await run_evaluation(doc_id)


@router.post("/compare/{doc_id}")
async def compare_retrieval_endpoint(doc_id: str, query: str):
    """Compare vector-only vs hybrid retrieval for a query."""
    _validate_doc_ready(doc_id)
    from app.retrieval.hybrid import compare_retrieval
    return await compare_retrieval(doc_id, query)


@router.post("/validate-reranker/{doc_id}")
async def validate_reranker_endpoint(doc_id: str, query: str):
    """Show before/after reranking for a query."""
    _validate_doc_ready(doc_id)
    from app.retrieval.hybrid import retrieve_for_task
    from app.evaluation.runner import validate_reranker
    chunks = await retrieve_for_task(doc_id, query, task_type="ask")
    return await validate_reranker(doc_id, query, chunks)


@router.post("/comparison-report/{doc_id}")
async def comparison_report_endpoint(doc_id: str):
    """Run retrieval comparison for standard test queries."""
    _validate_doc_ready(doc_id)
    from app.evaluation.runner import retrieval_comparison_report
    test_queries = [
        "What is machine learning?",
        "How does gradient descent work?",
        "Compare supervised and unsupervised learning",
        "What causes overfitting?",
        "Explain backpropagation",
    ]
    result = await retrieval_comparison_report(doc_id, test_queries)
    return {"report": result}


@router.get("/evaluation/report/{doc_id}")
async def get_evaluation_report(doc_id: str):
    """Get latest saved evaluation report."""
    from app.evaluation.final_report import get_latest_report
    report = get_latest_report(doc_id)
    if not report:
        raise HTTPException(404, "No evaluation report found. Run POST /api/evaluate/{doc_id} first.")
    return report


@router.get("/chunk-quality/{doc_id}")
async def get_chunk_quality(doc_id: str):
    """Validate chunk quality for a document."""
    _validate_doc_ready(doc_id)
    from app.chunking.validator import validate_chunks
    return validate_chunks(doc_id)


@router.get("/system/report/{doc_id}")
async def get_system_report(doc_id: str):
    """Get complete system validation report — combines all metrics."""
    _validate_doc_ready(doc_id)
    from app.evaluation.final_report import generate_system_report
    return await generate_system_report(doc_id)


@router.post("/evaluate/stable/{doc_id}")
async def evaluate_stable(doc_id: str, runs: int = 3):
    """Run multi-run evaluation for statistical stability."""
    _validate_doc_ready(doc_id)
    if runs < 3:
        raise HTTPException(400, "Minimum 3 runs required for statistical validity")
    from app.evaluation.runner import run_multi_evaluation
    from app.evaluation.final_report import generate_system_report
    stable_result = await run_multi_evaluation(doc_id, runs=runs)
    report = await generate_system_report(doc_id, stability_data=stable_result)
    return {"stability_evaluation": stable_result, "system_report": report}

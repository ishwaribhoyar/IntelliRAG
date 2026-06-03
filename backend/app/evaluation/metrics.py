"""Evaluation metrics — Recall@k, MRR, Accuracy, Hallucination rate, Not Found Accuracy."""
import logging

logger = logging.getLogger(__name__)


def recall_at_k(retrieved_ids: list[str], relevant_ids: list[str], k: int = 5) -> float:
    """Fraction of relevant documents found in top-k retrieved results."""
    if not relevant_ids:
        return 0.0
    top_k = set(retrieved_ids[:k])
    relevant = set(relevant_ids)
    return len(top_k & relevant) / len(relevant)


def mrr(retrieved_ids: list[str], relevant_ids: list[str]) -> float:
    """Mean Reciprocal Rank — 1/rank of first relevant result."""
    relevant = set(relevant_ids)
    for i, rid in enumerate(retrieved_ids):
        if rid in relevant:
            return 1.0 / (i + 1)
    return 0.0


def accuracy(predicted: list[str], ground_truth: list[str]) -> float:
    """Exact match accuracy between predicted and ground truth answers."""
    if not ground_truth:
        return 0.0
    correct = sum(
        1 for p, g in zip(predicted, ground_truth)
        if p.strip().lower() == g.strip().lower()
    )
    return correct / len(ground_truth)


def hallucination_rate(answers: list[str], contexts: list[str]) -> float:
    """Estimate hallucination rate — answers not grounded in context.

    Simple heuristic: check if key words from the answer appear in context.
    """
    if not answers:
        return 0.0

    hallucinated = 0
    for answer, context in zip(answers, contexts):
        answer_words = set(answer.lower().split())
        context_words = set(context.lower().split())
        # If less than 30% of answer words are in context, likely hallucinated
        if answer_words:
            overlap = len(answer_words & context_words) / len(answer_words)
            if overlap < 0.3:
                hallucinated += 1

    return hallucinated / len(answers)


def not_found_accuracy(answers: list[str], expected_not_found: list[bool]) -> float:
    """Accuracy of correctly returning 'not found' for out-of-scope queries."""
    if not expected_not_found:
        return 0.0

    not_found_phrases = {"not in document", "not found", "information not found", "could not be found"}
    correct = 0
    for answer, should_be_nf in zip(answers, expected_not_found):
        is_nf = any(phrase in answer.lower() for phrase in not_found_phrases)
        if is_nf == should_be_nf:
            correct += 1

    return correct / len(expected_not_found)


def compute_all_metrics(
    retrieved_ids_list: list[list[str]],
    relevant_ids_list: list[list[str]],
    predicted_answers: list[str],
    ground_truth_answers: list[str],
    contexts: list[str],
    expected_not_found: list[bool],
    k: int = 5,
) -> dict:
    """Compute all evaluation metrics at once.

    Returns dict with all metric values.
    """
    avg_recall = sum(
        recall_at_k(r, rel, k)
        for r, rel in zip(retrieved_ids_list, relevant_ids_list)
    ) / max(len(retrieved_ids_list), 1)

    avg_mrr = sum(
        mrr(r, rel)
        for r, rel in zip(retrieved_ids_list, relevant_ids_list)
    ) / max(len(retrieved_ids_list), 1)

    acc = accuracy(predicted_answers, ground_truth_answers)
    hall_rate = hallucination_rate(predicted_answers, contexts)
    nf_acc = not_found_accuracy(predicted_answers, expected_not_found)

    metrics = {
        f"recall@{k}": round(avg_recall, 4),
        "mrr": round(avg_mrr, 4),
        "accuracy": round(acc, 4),
        "hallucination_rate": round(hall_rate, 4),
        "not_found_accuracy": round(nf_acc, 4),
    }

    logger.info(f"Evaluation metrics: {metrics}")
    return metrics

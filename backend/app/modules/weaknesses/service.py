"""Weaknesses / Personalization module — service layer."""
import logging

from app.personalization.tracker import get_weak_topics, get_all_topic_scores
from app.personalization.advisor import generate_advice, generate_study_plan

logger = logging.getLogger(__name__)


async def handle_weakness_dashboard(user_id: str) -> dict:
    """Build weakness dashboard with enriched topic advice and study plan."""
    weak_topics = get_weak_topics(user_id)
    all_topics = get_all_topic_scores(user_id)

    enriched_weak = []
    for topic in weak_topics:
        advice = generate_advice(topic["topic"], topic.get("accuracy", 0), topic.get("trend", {}))
        enriched_weak.append({**topic, "advice": advice})

    study_plan = generate_study_plan(weak_topics)

    subject_summary = {}
    for row in all_topics:
        subj = row.get("subject", "General Studies")
        if subj not in subject_summary:
            subject_summary[subj] = {"subject": subj, "total": 0, "weak": 0, "moderate": 0, "strong": 0}
        subject_summary[subj]["total"] += 1
        st = row.get("status", "moderate")
        if st not in ("weak", "moderate", "strong"):
            st = "moderate"
        subject_summary[subj][st] += 1

    return {
        "user_id": user_id,
        "weak_topics": enriched_weak,
        "all_topics": all_topics,
        "study_plan": study_plan,
        "subject_summary": list(subject_summary.values()),
    }

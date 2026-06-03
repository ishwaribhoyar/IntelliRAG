"""Weakness advisor — generates actionable study insights.

Provides structured advice based on topic accuracy and trends.
No quiz re-runs — only insights, tips, and improvement plans.
"""
import logging

logger = logging.getLogger(__name__)


def generate_advice(topic: str, accuracy: float, trend: dict = None) -> dict:
    """Generate structured study advice for a weak topic.

    Args:
        topic: Topic name
        accuracy: Current accuracy (0.0 - 1.0)
        trend: Trend dict with 'direction' and 'improvement' keys

    Returns:
        Structured advice with issue, reason, improvement steps, and priority
    """
    direction = (trend or {}).get("direction", "stable")
    improvement = (trend or {}).get("improvement", 0)

    # Determine severity
    if accuracy < 0.3:
        severity = "critical"
        issue = f"You are struggling with '{topic}'"
        reason = "Your accuracy is very low — fundamental concepts may need review"
        steps = [
            f"Start with basic definitions of {topic}",
            "Read the relevant sections in your document carefully",
            "Use the 'Ask AI' feature to get explanations of key concepts",
            "Create flashcards for the core terms",
            "Take a focused quiz on just this topic",
        ]
    elif accuracy < 0.5:
        severity = "high"
        issue = f"'{topic}' needs significant improvement"
        reason = "You're getting less than half the questions right"
        steps = [
            f"Review the document sections about {topic}",
            "Focus on understanding 'why' — not just memorizing facts",
            "Use flashcards to reinforce weak areas",
            "Practice with targeted quiz questions",
        ]
    elif accuracy < 0.6:
        severity = "medium"
        issue = f"'{topic}' is below passing level"
        reason = "Close to mastery but still missing key concepts"
        steps = [
            "Review the questions you got wrong",
            f"Focus on the subtopics within {topic} that trip you up",
            "Try explaining the concept in your own words using Ask AI",
        ]
    else:
        severity = "low"
        issue = f"'{topic}' could use a bit more practice"
        reason = "You're close to mastery"
        steps = [
            "Review edge cases and advanced details",
            "Challenge yourself with harder questions",
        ]

    # Adjust based on trend
    if direction == "improving":
        trend_note = "📈 You're improving — keep up the momentum!"
    elif direction == "declining":
        trend_note = "📉 Your performance is declining — revisit the basics"
        steps.insert(0, "Go back to fundamentals before attempting harder questions")
    else:
        trend_note = "→ Your performance is stable — focus on weak sub-areas"

    return {
        "issue": issue,
        "reason": reason,
        "severity": severity,
        "improvement": steps,
        "trend_note": trend_note,
        "priority": "high" if accuracy < 0.4 else "medium" if accuracy < 0.6 else "low",
    }


def generate_study_plan(weak_topics: list[dict]) -> dict:
    """Generate a prioritized study plan from all weak topics.

    Args:
        weak_topics: List of weak topic dicts with accuracy, topic, trend

    Returns:
        Study plan with ordered priorities and time estimates
    """
    if not weak_topics:
        return {
            "status": "all_clear",
            "message": "Great job! No weak areas detected. Keep practicing to maintain your skills.",
            "plan": [],
        }

    # Sort by accuracy (weakest first)
    sorted_topics = sorted(weak_topics, key=lambda t: t.get("accuracy", 0))

    plan = []
    for i, topic in enumerate(sorted_topics):
        accuracy = topic.get("accuracy", 0)
        advice = generate_advice(
            topic["topic"],
            accuracy,
            topic.get("trend", {}),
        )
        plan.append({
            "order": i + 1,
            "topic": topic["topic"],
            "accuracy": accuracy,
            "advice": advice,
            "estimated_sessions": 3 if accuracy < 0.3 else 2 if accuracy < 0.5 else 1,
        })

    return {
        "status": "needs_work",
        "total_weak": len(plan),
        "critical_count": sum(1 for p in plan if p["advice"]["severity"] == "critical"),
        "plan": plan,
    }

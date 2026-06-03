"""
features.quiz_engine
====================
Top-level feature: Quiz Engine

Business capability: Generate, grade, and track quizzes, MCQs, flashcards,
fill-in-the-blank, rapid-fire games, and summaries from document content.

Sub-features mapped to existing modules
-----------------------------------------
quiz_generation      → app.generators.quiz           (quiz + MCQ generation)
question_generation  → app.generators.content        (content/summary generation)
mcq_generation       → app.generators.games          (game-style interactive MCQs)
flashcards           → app.modules.flashcards         (flashcard routes + service)
mock_tests           → app.generators.games           (rapid-fire, true/false)
summaries            → app.generators.content         (summary generation)
scoring              → app.gamification.engine        (XP scoring)
prompt_management    → app.generators.prompts         (quiz/flashcard prompts)
grading              → (stub — future LLM grading)
retry                → (stub — future retry logic)
refresh              → (stub — future content refresh)
analytics            → app.modules.analytics          (quiz analytics)
"""

from app.modules.quizzes.routes import router as quiz_router               # noqa: F401
from app.modules.quizzes.service import handle_quiz_start, handle_quiz_submit  # noqa: F401
from app.modules.flashcards.routes import router as flashcards_router      # noqa: F401
from app.generators.quiz import generate_quiz, evaluate_quiz               # noqa: F401
from app.generators.content import generate_content, ask_mentor            # noqa: F401
from app.generators.prompts import get_prompt, QUIZ_PROMPT, FLASHCARD_PROMPT  # noqa: F401

__all__ = [
    "quiz_router",
    "handle_quiz_start",
    "handle_quiz_submit",
    "flashcards_router",
    "generate_quiz",
    "evaluate_quiz",
    "generate_content",
    "ask_mentor",
    "get_prompt",
    "QUIZ_PROMPT",
    "FLASHCARD_PROMPT",
]

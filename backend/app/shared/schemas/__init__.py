"""Shared schemas — package init. Imports all schema types for convenience."""
from app.shared.schemas.auth import AuthRequest
from app.shared.schemas.ask import AskRequest, MentorRequest
from app.shared.schemas.quiz import QuizStartRequest, QuizSubmitRequest
from app.shared.schemas.generate import GenerateRequest
from app.shared.schemas.search import SearchRequest, UserSearchRequest
from app.shared.schemas.library import LibraryAddRequest, LibraryRemoveRequest
from app.shared.schemas.course import CourseActionRequest, CourseChatRequest

__all__ = [
    "AuthRequest",
    "AskRequest", "MentorRequest",
    "QuizStartRequest", "QuizSubmitRequest",
    "GenerateRequest",
    "SearchRequest", "UserSearchRequest",
    "LibraryAddRequest", "LibraryRemoveRequest",
    "CourseActionRequest", "CourseChatRequest",
]

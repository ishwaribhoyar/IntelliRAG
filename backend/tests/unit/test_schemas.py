"""Unit tests — Shared schemas."""
import pytest
from app.shared.schemas.ask import AskRequest, MentorRequest
from app.shared.schemas.quiz import QuizStartRequest, QuizSubmitRequest
from app.shared.schemas.generate import GenerateRequest
from app.shared.schemas.search import SearchRequest, UserSearchRequest


def test_ask_request_defaults():
    req = AskRequest(user_id="u1", query="What is RAG?")
    assert req.user_id == "u1"
    assert req.query == "What is RAG?"
    assert req.llm_variant == "30b"
    assert req.doc_id is None


def test_ask_request_alias():
    """query and question are both accepted."""
    req = AskRequest(user_id="u1", question="What is RAG?")
    assert req.question == "What is RAG?"


def test_quiz_submit_defaults():
    req = QuizSubmitRequest(
        doc_id="doc_123",
        questions=[{"question": "Q1"}],
        answers=["A"],
    )
    assert req.quiz_type == "quiz"
    assert req.user_id == "default_user"


def test_search_request_defaults():
    req = SearchRequest(doc_id="doc_abc", query="machine learning")
    assert req.mode == "auto"
    assert req.user_id == "default_user"


def test_generate_request():
    req = GenerateRequest(doc_id="doc_abc", content_type="flashcards")
    assert req.content_type == "flashcards"
    assert req.refresh == False

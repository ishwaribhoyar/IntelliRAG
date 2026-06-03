"""Unit/Integration tests — Premium-Only Restrictions."""
import pytest
from unittest.mock import patch
from fastapi import HTTPException
from fastapi.testclient import TestClient
from app.main import app
from app.shared.database import SessionLocal, User

TEST_FREE_USER_ID = "test_premium_free_user"
TEST_PREMIUM_USER_ID = "test_premium_prem_user"


@pytest.fixture(autouse=True)
def setup_users():
    """Create test users in DB before test and delete after."""
    db = SessionLocal()
    try:
        # Delete any existing
        db.query(User).filter(User.id.in_([TEST_FREE_USER_ID, TEST_PREMIUM_USER_ID])).delete()
        db.commit()
        
        # Create users
        free_user = User(id=TEST_FREE_USER_ID, name="Free User", username="free_user", tier="free")
        prem_user = User(id=TEST_PREMIUM_USER_ID, name="Premium User", username="prem_user", tier="premium")
        db.add_all([free_user, prem_user])
        db.commit()
    finally:
        db.close()
        
    yield
    
    db = SessionLocal()
    try:
        db.query(User).filter(User.id.in_([TEST_FREE_USER_ID, TEST_PREMIUM_USER_ID])).delete()
        db.commit()
    finally:
        db.close()


def test_ask_cross_document_blocks_free_user():
    """POST /api/ask blocks cross-document queries (no doc_id) for free users."""
    client = TestClient(app)
    response = client.post(
        "/api/ask",
        json={
            "user_id": TEST_FREE_USER_ID,
            "query": "What is AI?",
            "doc_id": None
        }
    )
    assert response.status_code == 403
    assert "Multi-PDF cross-document reasoning is a Premium-only feature" in response.json()["detail"]


def test_ask_cross_document_allows_premium_user():
    """POST /api/ask allows cross-document queries (no doc_id) for premium users."""
    client = TestClient(app)
    
    with patch("app.modules.ask_ai.routes.handle_ask") as mock_handle:
        mock_handle.return_value = {"answer": "mocked answer"}
        response = client.post(
            "/api/ask",
            json={
                "user_id": TEST_PREMIUM_USER_ID,
                "query": "What is AI?",
                "doc_id": None
            }
        )
        assert response.status_code == 200
        assert response.json() == {"answer": "mocked answer"}


def test_ask_single_document_allows_free_user():
    """POST /api/ask allows single document query (doc_id provided) for free users."""
    client = TestClient(app)
    
    with patch("app.modules.ask_ai.routes.handle_ask") as mock_handle:
        mock_handle.return_value = {"answer": "mocked answer"}
        response = client.post(
            "/api/ask",
            json={
                "user_id": TEST_FREE_USER_ID,
                "query": "What is AI?",
                "doc_id": "some_doc_id"
            }
        )
        assert response.status_code == 200
        assert response.json() == {"answer": "mocked answer"}


def test_mentor_chat_blocks_free_user():
    """POST /api/mentor blocks AI Mentor mode for non-premium users."""
    client = TestClient(app)
    response = client.post(
        "/api/mentor",
        json={
            "user_id": TEST_FREE_USER_ID,
            "doc_id": "some_doc_id",
            "question": "Please explain this"
        }
    )
    assert response.status_code == 403
    assert "AI Study Coach (Mentor Chat) is a Premium-only feature" in response.json()["detail"]


def test_mentor_chat_allows_premium_user():
    """POST /api/mentor allows AI Mentor mode for premium users."""
    client = TestClient(app)
    
    with patch("app.modules.ask_ai.routes.handle_mentor") as mock_handle:
        mock_handle.return_value = {"answer": "mentor answer"}
        response = client.post(
            "/api/mentor",
            json={
                "user_id": TEST_PREMIUM_USER_ID,
                "doc_id": "some_doc_id",
                "question": "Please explain this"
            }
        )
        assert response.status_code == 200
        assert response.json() == {"answer": "mentor answer"}

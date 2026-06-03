"""Unit tests — Rate Limiter."""
import pytest
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

from app.shared.database import SessionLocal, User
from app.shared.utils.rate_limiter import check_and_update_rate_limit, FREE_TIER_LIMITS

TEST_USER_ID = "test_rate_limiter_user"


@pytest.fixture(autouse=True)
def cleanup_user():
    """Ensure the test user is removed before and after each test."""
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == TEST_USER_ID).delete()
        db.commit()
    finally:
        db.close()
        
    yield
    
    db = SessionLocal()
    try:
        db.query(User).filter(User.id == TEST_USER_ID).delete()
        db.commit()
    finally:
        db.close()


def test_rate_limiter_free_tier_limits():
    """Free tier users are rate limited per operation type."""
    # First request: check_and_update_rate_limit creates the user and increments count
    check_and_update_rate_limit(TEST_USER_ID, "quiz")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == TEST_USER_ID).first()
        assert user is not None
        assert user.tier == "free"
        assert user.daily_quiz_count == 1
    finally:
        db.close()
        
    # Second request: allowed (limit is 2)
    check_and_update_rate_limit(TEST_USER_ID, "quiz")
    
    # Third request: should raise 429
    with pytest.raises(HTTPException) as exc_info:
        check_and_update_rate_limit(TEST_USER_ID, "quiz")
    assert exc_info.value.status_code == 429
    assert "Daily limit" in exc_info.value.detail


def test_rate_limiter_premium_tier_bypass():
    """Standard and Premium tier users bypass the rate limiter completely."""
    # Pre-create the user as premium
    db = SessionLocal()
    try:
        user = User(id=TEST_USER_ID, name="Premium Test", username="premium_test", tier="premium")
        db.add(user)
        db.commit()
    finally:
        db.close()
        
    # Query many times (beyond standard free limit of 2)
    for _ in range(10):
        check_and_update_rate_limit(TEST_USER_ID, "quiz")
        
    # Should not raise any exception, and count shouldn't have changed
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == TEST_USER_ID).first()
        assert user.tier == "premium"
        assert user.daily_quiz_count == 0  # Premium doesn't increment/use free quota columns
    finally:
        db.close()


def test_rate_limiter_day_boundary_reset():
    """Daily limit counters reset on a new day boundary."""
    db = SessionLocal()
    try:
        # Pre-create user with usage counts, but reset date set to yesterday
        yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        user = User(
            id=TEST_USER_ID,
            name="Free Test",
            username="free_test",
            tier="free",
            daily_rag_count=5,
            daily_quiz_count=2,
            last_request_reset=yesterday_str
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
        
    # Since last_request_reset is yesterday, the next request resets counts and succeeds
    check_and_update_rate_limit(TEST_USER_ID, "quiz")
    
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == TEST_USER_ID).first()
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert user.last_request_reset == today_str
        assert user.daily_quiz_count == 1  # Reset to 0 then incremented to 1
        assert user.daily_rag_count == 0   # Reset to 0
    finally:
        db.close()

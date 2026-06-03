"""Unit tests — LLM Router."""
import pytest


def test_llm_router_default_provider():
    """LLM Router defaults to Sarvam when LLM_PROVIDER is unset."""
    import os
    os.environ.pop("LLM_PROVIDER", None)
    from app.modules.llm_router.router import LLMRouter
    router = LLMRouter()
    assert router.provider.provider_name == "sarvam"


def test_llm_router_switch_provider():
    """LLMRouter.switch_provider() changes the active provider."""
    from app.modules.llm_router.router import LLMRouter
    router = LLMRouter()
    # Switching to groq returns a GroqProvider
    router.switch_provider("groq")
    assert router.provider.provider_name == "groq"
    # Switch back to sarvam
    router.switch_provider("sarvam")
    assert router.provider.provider_name == "sarvam"


def test_llm_router_unknown_provider_falls_back():
    """Unknown provider name falls back to Sarvam with a warning."""
    from app.modules.llm_router.router import LLMRouter
    router = LLMRouter()
    router.switch_provider("banana_provider")
    assert router.provider.provider_name == "sarvam"


def test_llm_router_balanced_routing():
    """LLMRouter routes task_types appropriately in 'balanced' mode based on user tier."""
    from app.modules.llm_router.router import LLMRouter
    router = LLMRouter()
    router.switch_provider("balanced")
    
    # --- FREE TIER ---
    # RAG & Summaries -> gemini
    assert router.route_task("ask", "free") == "gemini"
    assert router.route_task("summary", "free") == "gemini"
    
    # Quizzes & Flashcards -> openai
    assert router.route_task("quiz", "free") == "openai"
    assert router.route_task("mock_test", "free") == "openai"
    assert router.route_task("flashcards", "free") == "openai"
    
    # Reranker -> local_bge
    assert router.route_task("rerank", "free") == "local_bge"
    
    # Other fallback -> gemini
    assert router.route_task("random_unknown_task", "free") == "gemini"

    # --- PREMIUM TIER ---
    # RAG & Summaries -> openai
    assert router.route_task("ask", "premium") == "openai"
    assert router.route_task("summary", "premium") == "openai"
    
    # Quizzes & Flashcards -> gemini
    assert router.route_task("quiz", "premium") == "gemini"
    assert router.route_task("mock_test", "premium") == "gemini"
    assert router.route_task("flashcards", "premium") == "gemini"
    
    # Reranker -> local_bge
    assert router.route_task("rerank", "premium") == "local_bge"
    
    # Other fallback -> gemini
    assert router.route_task("random_unknown_task", "premium") == "gemini"

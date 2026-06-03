"""
features.llm_platform
======================
Top-level feature: LLM Platform

Business capability: Abstract and route LLM calls across multiple providers
(Gemini, OpenAI, Anthropic, Groq, Ollama, OpenRouter, Sarvam) with
fallback chain, prompt management, and extensible provider interface.

Sub-features mapped to existing modules
-----------------------------------------
providers        → app.modules.llm_router.providers  (all provider implementations)
model_router     → app.modules.llm_router.router     (provider selection — LLMRouter)
prompt_management→ app.generators.prompts            (prompt templates)
fallback         → app.modules.llm_router.router     (fallback chain in LLMRouter)
streaming        → (stub — future streaming support)
token_tracking   → (stub — future token accounting)
cost_tracking    → (stub — future cost tracking)
provider_metrics → (stub — future per-provider metrics)
"""

from app.modules.llm_router.router import LLMRouter                  # noqa: F401
from app.modules.llm_router.base import LLMProvider                  # noqa: F401
from app.generators.prompts import get_prompt, build_refresh_instruction  # noqa: F401
from app.rag.llm_client import call_llm                              # noqa: F401

__all__ = [
    "LLMRouter",
    "LLMProvider",
    "get_prompt",
    "build_refresh_instruction",
    "call_llm",
]

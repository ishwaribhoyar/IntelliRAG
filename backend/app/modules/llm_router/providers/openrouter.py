"""OpenRouter provider — stub. Set LLM_PROVIDER=openrouter + OPENROUTER_API_KEY."""
from app.modules.llm_router.base import LLMProvider
from typing import Any

class OpenRouterProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "openrouter"

    async def generate(self, doc_id, task_type, prompt, context, stream=False,
                       use_cache=True, temperature=None, max_tokens=None, llm_variant=None) -> dict[str, Any]:
        """TODO: Implement OpenRouter API (OpenAI-compatible). Base URL: https://openrouter.ai/api/v1."""
        raise NotImplementedError("OpenRouter provider not yet implemented.")

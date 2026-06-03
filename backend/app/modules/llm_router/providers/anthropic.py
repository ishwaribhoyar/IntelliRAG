"""Anthropic Claude provider — stub. Set LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY."""
from app.modules.llm_router.base import LLMProvider
from typing import Any

class AnthropicProvider(LLMProvider):
    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def generate(self, doc_id, task_type, prompt, context, stream=False,
                       use_cache=True, temperature=None, max_tokens=None, llm_variant=None) -> dict[str, Any]:
        """TODO: Implement Anthropic Messages API. Model: claude-3-5-sonnet-20241022."""
        raise NotImplementedError("Anthropic provider not yet implemented.")

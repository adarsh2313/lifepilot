import logging

from openai import AsyncOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from backend.llm.base import LLMProvider, Message

logger = logging.getLogger(__name__)

# Known OpenRouter base URL for provider_name display
_OPENROUTER_HOST = "openrouter.ai"
_GROQ_HOST = "api.groq.com"
_OLLAMA_PORT = "11434"
_LM_STUDIO_PORT = "1234"


class OpenAICompatibleProvider(LLMProvider):
    """LLM provider for any OpenAI-compatible API.

    Covers:
      - OpenAI:      base_url=None,                                 api_key="sk-..."
      - OpenRouter:  base_url="https://openrouter.ai/api/v1",       api_key="sk-or-..."
      - Groq:        base_url="https://api.groq.com/openai/v1",     api_key="gsk_..."
      - Ollama:      base_url="http://localhost:11434/v1",           api_key=""
      - LM Studio:   base_url="http://localhost:1234/v1",            api_key="none"
    """

    def __init__(self, api_key: str, model: str, base_url: str | None = None):
        self.client = AsyncOpenAI(
            api_key=api_key or "none",  # local providers don't need a real key
            base_url=base_url,
        )
        self.model = model
        self._base_url = base_url or ""

    def provider_name(self) -> str:
        url = self._base_url
        if _OPENROUTER_HOST in url:
            return f"OpenRouter ({self.model})"
        if _GROQ_HOST in url:
            return f"Groq ({self.model})"
        if _OLLAMA_PORT in url:
            return f"Ollama ({self.model})"
        if _LM_STUDIO_PORT in url:
            return f"LM Studio ({self.model})"
        return f"OpenAI ({self.model})"

    async def chat(self, messages: list[Message], system: str) -> str:
        return await self._chat_with_retry(messages, system)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _chat_with_retry(self, messages: list[Message], system: str) -> str:
        all_messages = [{"role": "system", "content": system}] + messages

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=all_messages,
            temperature=0.7,
            max_tokens=1024,
        )

        return response.choices[0].message.content

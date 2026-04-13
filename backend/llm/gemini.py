import asyncio
import logging

from google import genai
from google.genai import types as genai_types
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from backend.llm.base import LLMProvider, Message

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """LLM provider backed by Google Gemini."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash-preview-04-17"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def provider_name(self) -> str:
        return f"Gemini ({self.model})"

    async def chat(self, messages: list[Message], system: str) -> str:
        return await self._chat_with_retry(messages, system)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _chat_with_retry(self, messages: list[Message], system: str) -> str:
        # Gemini uses "model" instead of "assistant" for the AI role
        contents = [
            genai_types.Content(
                role="user" if m["role"] == "user" else "model",
                parts=[genai_types.Part(text=m["content"])],
            )
            for m in messages
        ]

        config = genai_types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.7,
            max_output_tokens=1024,
        )

        # google-genai SDK doesn't have native async — run in executor
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=config,
            ),
        )

        return response.text

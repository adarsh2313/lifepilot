from abc import ABC, abstractmethod

Message = dict  # {"role": "user" | "assistant", "content": str}


class LLMProvider(ABC):
    """Abstract base for all LLM providers.
    All coach sessions call provider.chat() — never touch a provider SDK directly.
    Swapping Gemini → Ollama → OpenRouter is one config.json line change.
    """

    @abstractmethod
    async def chat(self, messages: list[Message], system: str) -> str:
        """
        Args:
            messages: conversation history as [{"role": "user"|"assistant", "content": "..."}]
            system:   system prompt string
        Returns:
            The assistant's response as a plain string.
        """
        ...

    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable name for logging and UI display."""
        ...

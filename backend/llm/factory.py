from backend.llm.base import LLMProvider
from backend.llm.gemini import GeminiProvider
from backend.llm.openai_compat import OpenAICompatibleProvider


def get_provider(config: dict) -> LLMProvider:
    """Factory: reads config dict → returns the correct LLMProvider instance.

    Config examples:
      Gemini:      {"provider": "gemini",     "api_key": "AIza...", "model": "gemini-2.5-flash-preview-04-17"}
      OpenAI:      {"provider": "openai",     "api_key": "sk-...",  "model": "gpt-4o"}
      OpenRouter:  {"provider": "openrouter", "api_key": "sk-or-...", "model": "qwen/qwen3-235b-a22b"}
      Groq:        {"provider": "groq",       "api_key": "gsk_...", "model": "llama-3.3-70b-versatile"}
      Ollama:      {"provider": "ollama",     "api_key": "",        "model": "llama3", "base_url": "http://localhost:11434/v1"}
      LM Studio:   {"provider": "lmstudio",   "api_key": "none",    "model": "...",    "base_url": "http://localhost:1234/v1"}
    """
    provider = config.get("provider", "gemini")
    api_key = config.get("api_key", "")
    model = config.get("model", "gemini-2.5-flash-preview-04-17")
    base_url = config.get("base_url", None)

    match provider:
        case "gemini":
            return GeminiProvider(api_key=api_key, model=model)

        case "openai":
            return OpenAICompatibleProvider(api_key=api_key, model=model)

        case "openrouter":
            return OpenAICompatibleProvider(
                api_key=api_key,
                model=model,
                base_url=base_url or "https://openrouter.ai/api/v1",
            )

        case "groq":
            return OpenAICompatibleProvider(
                api_key=api_key,
                model=model,
                base_url=base_url or "https://api.groq.com/openai/v1",
            )

        case "ollama":
            return OpenAICompatibleProvider(
                api_key="none",
                model=model,
                base_url=base_url or "http://localhost:11434/v1",
            )

        case "lmstudio":
            return OpenAICompatibleProvider(
                api_key="none",
                model=model,
                base_url=base_url or "http://localhost:1234/v1",
            )

        case _:
            # Treat unknown providers as OpenAI-compatible with explicit base_url
            return OpenAICompatibleProvider(api_key=api_key, model=model, base_url=base_url)

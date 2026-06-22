from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.utils.logging import get_logger

log = get_logger(__name__)


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
                                                                            
                                                                          
    finish_reason: str = ""
    truncated: bool = False


class LLMProvider(ABC):
    name: str = "base"

                                                                       
    def __init__(self, model: str, temperature: float = 0.1, max_tokens: int = 8192) -> None:
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    @abstractmethod
    def complete(self, system: str, user: str) -> LLMResponse: ...

    def is_available(self) -> bool:
        return False


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, model: str = "gpt-4o", temperature: float = 0.1, max_tokens: int = 8192) -> None:
        super().__init__(model, temperature, max_tokens)
        self._client = None

    def is_available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ImportError("openai package is required for OpenAIProvider") from exc
            self._client = OpenAI()
        return self._client

    def complete(self, system: str, user: str) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("OPENAI_API_KEY is not set")
        client = self._get_client()
        result = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice_msg = result.choices[0]
        choice = choice_msg.message.content or ""
        usage = getattr(result, "usage", None)
        finish_reason = getattr(choice_msg, "finish_reason", "") or ""
        return LLMResponse(
            text=choice,
            provider=self.name,
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            finish_reason=finish_reason,
            truncated=(finish_reason == "length"),
        )


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(
        self, model: str = "claude-opus-4-7", temperature: float = 0.1, max_tokens: int = 8192
    ) -> None:
        super().__init__(model, temperature, max_tokens)
        self._client = None

    def is_available(self) -> bool:
        return bool(os.getenv("ANTHROPIC_API_KEY"))

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:
                raise ImportError("anthropic package is required for AnthropicProvider") from exc
            self._client = anthropic.Anthropic()
        return self._client

    def complete(self, system: str, user: str) -> LLMResponse:
        if not self.is_available():
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        client = self._get_client()
        result = client.messages.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text_blocks = [b.text for b in result.content if getattr(b, "type", None) == "text"]
        stop_reason = getattr(result, "stop_reason", "") or ""
        return LLMResponse(
            text="\n".join(text_blocks),
            provider=self.name,
            model=self.model,
            prompt_tokens=result.usage.input_tokens if getattr(result, "usage", None) else 0,
            completion_tokens=result.usage.output_tokens if getattr(result, "usage", None) else 0,
            finish_reason=stop_reason,
            truncated=(stop_reason == "max_tokens"),
        )


class _OpenAICompatProvider(LLMProvider):

    name = "local"
    default_base_url = "http://localhost:11434/v1"
    default_model = "qwen2.5-coder:7b"
    env_base_url = "LOCAL_LLM_BASE_URL"
    env_model = "LOCAL_LLM_MODEL"
    _reachable: bool | None = None

    def __init__(self, model: str | None = None, temperature: float = 0.1, max_tokens: int = 8192) -> None:
        model = model or os.getenv(self.env_model) or self.default_model
        super().__init__(model, temperature, max_tokens)
        self.base_url = os.getenv(self.env_base_url, self.default_base_url)
        self._client = None

    def is_available(self) -> bool:
        if self._reachable is not None:
            return self._reachable
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(self.base_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            with socket.create_connection((host, port), timeout=1.5):
                type(self)._reachable = True
        except OSError:
            type(self)._reachable = False
        return bool(type(self)._reachable)

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ImportError("openai package is required for the local provider") from exc
            self._client = OpenAI(base_url=self.base_url, api_key=os.getenv("LOCAL_LLM_API_KEY", "local"))
        return self._client

    def complete(self, system: str, user: str) -> LLMResponse:
        client = self._get_client()
        result = client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        choice_msg = result.choices[0]
        text = choice_msg.message.content or ""
        usage = getattr(result, "usage", None)
        finish_reason = getattr(choice_msg, "finish_reason", "") or ""
        return LLMResponse(
            text=text,
            provider=self.name,
            model=self.model,
            prompt_tokens=getattr(usage, "prompt_tokens", 0) if usage else 0,
            completion_tokens=getattr(usage, "completion_tokens", 0) if usage else 0,
            finish_reason=finish_reason,
            truncated=(finish_reason == "length"),
        )


class OllamaProvider(_OpenAICompatProvider):
    name = "ollama"
    default_base_url = "http://localhost:11434/v1"
    default_model = "qwen2.5-coder:7b"


class VLLMProvider(_OpenAICompatProvider):
    name = "vllm"
    default_base_url = "http://localhost:8000/v1"
    default_model = "meta-llama/Llama-3.1-8B-Instruct"


def get_provider(name: str, **kwargs) -> LLMProvider:
    name = name.lower()
    if name == "openai":
        return OpenAIProvider(**kwargs)
    if name == "anthropic":
        return AnthropicProvider(**kwargs)
    if name == "ollama":
        return OllamaProvider(**kwargs)
    if name in {"vllm", "local"}:
        return VLLMProvider(**kwargs) if name == "vllm" else _OpenAICompatProvider(**kwargs)
    raise ValueError(f"Unknown provider: {name}")

"""Thin wrapper around the Ollama chat API."""

from collections.abc import Iterator
from dataclasses import dataclass, field

import ollama


class LLMError(Exception):
    """Raised when the local model cannot be reached or used."""


@dataclass(frozen=True)
class ToolCall:
    """A request from the model to run a tool."""

    name: str
    arguments: dict = field(default_factory=dict)


class OllamaClient:
    def __init__(self, model: str) -> None:
        self.model = model
        self._client = ollama.Client()

    def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> Iterator[str | ToolCall]:
        """Stream the reply to `messages`: text chunks, plus a ToolCall for each tool requested."""
        try:
            for part in self._client.chat(
                model=self.model, messages=messages, tools=tools or None, stream=True
            ):
                if part.message.content:
                    yield part.message.content
                for call in part.message.tool_calls or []:
                    yield ToolCall(call.function.name, dict(call.function.arguments or {}))
        except ollama.ResponseError as exc:
            if exc.status_code == 404:
                raise LLMError(
                    f"Model '{self.model}' is not installed. Run: ollama pull {self.model}"
                ) from exc
            raise LLMError(f"Ollama error: {exc.error}") from exc
        except (ConnectionError, ollama.RequestError) as exc:
            raise LLMError(
                "Cannot reach Ollama. Is it running? Start it from the Start menu or `ollama serve`."
            ) from exc

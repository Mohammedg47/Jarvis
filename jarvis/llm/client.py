"""Thin wrapper around the Ollama chat API."""

import logging
from collections.abc import Iterator
from dataclasses import dataclass, field

import ollama

logger = logging.getLogger("jarvis.llm")


class LLMError(Exception):
    """Raised when the local model cannot be reached or used."""


@dataclass(frozen=True)
class ToolCall:
    """A request from the model to run a tool."""

    name: str
    arguments: dict = field(default_factory=dict)


class OllamaClient:
    def __init__(self, model: str, keep_alive: str = "30m") -> None:
        self.model = model
        # How long Ollama keeps the model in memory after a request: "30m", "-1" (forever)...
        self.keep_alive: str | int = (
            int(keep_alive) if keep_alive.lstrip("-").isdigit() else keep_alive
        )
        self._client = ollama.Client()

    def warm_up(self, messages: list[dict], tools: list[dict] | None = None) -> None:
        """Load the model and read the prompt now, so the first real message is fast. Errors
        are ignored: if Ollama is down the first message reports it."""
        try:
            self._client.chat(
                model=self.model,
                messages=messages,
                tools=tools or None,
                options={"num_predict": 1},
                keep_alive=self.keep_alive,
            )
        except Exception:
            logger.info("Model warm-up skipped", exc_info=True)

    def chat(
        self, messages: list[dict], tools: list[dict] | None = None
    ) -> Iterator[str | ToolCall]:
        """Stream the reply to `messages`: text chunks, plus a ToolCall for each tool requested."""
        try:
            for part in self._client.chat(
                model=self.model,
                messages=messages,
                tools=tools or None,
                stream=True,
                keep_alive=self.keep_alive,
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

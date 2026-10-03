"""Thin wrapper around the Ollama chat API."""

from collections.abc import Iterator

import ollama


class LLMError(Exception):
    """Raised when the local model cannot be reached or used."""


class OllamaClient:
    def __init__(self, model: str) -> None:
        self.model = model
        self._client = ollama.Client()

    def chat(self, messages: list[dict]) -> Iterator[str]:
        """Stream the reply to `messages` as text chunks."""
        try:
            for part in self._client.chat(model=self.model, messages=messages, stream=True):
                yield part.message.content or ""
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

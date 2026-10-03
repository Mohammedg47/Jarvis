"""Conversation state: the message history exchanged with the LLM."""

from collections.abc import Callable, Iterator


class Conversation:
    def __init__(self, chat: Callable[[list[dict]], Iterator[str]], system_prompt: str) -> None:
        self._chat = chat
        self._system = {"role": "system", "content": system_prompt}
        self.messages: list[dict] = [self._system]

    def send(self, text: str) -> Iterator[str]:
        """Add the user's message, stream the reply, then record it in the history."""
        self.messages.append({"role": "user", "content": text})
        reply: list[str] = []
        try:
            for chunk in self._chat(self.messages):
                reply.append(chunk)
                yield chunk
        except BaseException:
            self.messages.pop()  # do not keep a user message that got no answer
            raise
        self.messages.append({"role": "assistant", "content": "".join(reply)})

    def clear(self) -> None:
        self.messages = [self._system]

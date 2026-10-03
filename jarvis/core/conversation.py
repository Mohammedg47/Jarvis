"""Conversation state: the message history exchanged with the LLM."""

from collections.abc import Callable, Iterator

from jarvis.llm.client import ToolCall
from jarvis.tools.gate import ToolRunner

MAX_TOOL_ROUNDS = 5  # stops a model that keeps calling tools without ever answering


class Conversation:
    def __init__(
        self,
        chat: Callable[..., Iterator[str | ToolCall]],
        system_prompt: str,
        tools: ToolRunner | None = None,
    ) -> None:
        self._chat = chat
        self._tools = tools
        self._system = {"role": "system", "content": system_prompt}
        self.messages: list[dict] = [self._system]

    def send(self, text: str) -> Iterator[str]:
        """Add the user's message and stream the reply, running any tools the model calls."""
        start = len(self.messages)
        self.messages.append({"role": "user", "content": text})
        try:
            for _ in range(MAX_TOOL_ROUNDS):
                reply: list[str] = []
                calls: list[ToolCall] = []
                for chunk in self._stream():
                    if isinstance(chunk, ToolCall):
                        calls.append(chunk)
                    else:
                        reply.append(chunk)
                        yield chunk
                message: dict = {"role": "assistant", "content": "".join(reply)}
                if not calls or self._tools is None:
                    self.messages.append(message)
                    return
                message["tool_calls"] = [
                    {"function": {"name": c.name, "arguments": c.arguments}} for c in calls
                ]
                self.messages.append(message)
                for call in calls:
                    result = self._tools.run(call.name, call.arguments)
                    self.messages.append(
                        {"role": "tool", "tool_name": call.name, "content": result}
                    )
            notice = "I could not finish that: too many tool steps."
            self.messages.append({"role": "assistant", "content": notice})
            yield notice
        except BaseException:
            del self.messages[start:]  # drop the unanswered turn, including partial tool steps
            raise

    def _stream(self) -> Iterator[str | ToolCall]:
        if self._tools is None:
            return self._chat(self.messages)
        return self._chat(self.messages, tools=self._tools.schemas())

    def clear(self) -> None:
        self.messages = [self._system]

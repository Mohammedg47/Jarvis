"""Conversation state: the message history exchanged with the LLM."""

from collections.abc import Callable, Iterator

from jarvis.llm.client import ToolCall
from jarvis.memory import MemoryStore
from jarvis.tools.gate import ToolRunner

MAX_TOOL_ROUNDS = 5  # stops a model that keeps calling tools without ever answering
HISTORY_MESSAGES = 20  # how many saved messages are loaded into a new session


class Conversation:
    def __init__(
        self,
        chat: Callable[..., Iterator[str | ToolCall]],
        system_prompt: str,
        tools: ToolRunner | None = None,
        memory: MemoryStore | None = None,
    ) -> None:
        self._chat = chat
        self._tools = tools
        self._memory = memory
        self._prompt = system_prompt
        self.messages: list[dict] = [self._system_message()]
        if memory is not None:
            self.messages.extend(memory.recent_messages(HISTORY_MESSAGES))

    def _system_message(self) -> dict:
        """The system prompt, plus whatever the user asked Jarvis to remember."""
        content = self._prompt
        prefs = self._memory.preferences() if self._memory is not None else {}
        if prefs:
            lines = "\n".join(f"- {k}: {v}" for k, v in prefs.items())
            content += f"\n\nThings the user asked you to remember:\n{lines}"
        return {"role": "system", "content": content}

    def _save(self, start: int) -> None:
        """Persist the finished turn: the user's message and the final reply, not tool steps."""
        if self._memory is None:
            return
        used_tools = any(m.get("tool_calls") for m in self.messages[start:])
        for message in self.messages[start:]:
            is_chat = message["role"] in ("user", "assistant") and not message.get("tool_calls")
            if is_chat and message["content"]:
                self._memory.add_message(message["role"], message["content"], used_tools)

    def send(self, text: str) -> Iterator[str]:
        """Add the user's message and stream the reply, running any tools the model calls."""
        self.messages[0] = self._system_message()  # pick up preferences saved since last turn
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
                    self._save(start)
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
            self._save(start)
            yield notice
        except BaseException:
            del self.messages[start:]  # drop the unanswered turn, including partial tool steps
            raise

    def _stream(self) -> Iterator[str | ToolCall]:
        if self._tools is None:
            return self._chat(self.messages)
        return self._chat(self.messages, tools=self._tools.schemas())

    def set_system_prompt(self, system_prompt: str) -> None:
        """Swap the system prompt (e.g. a personality change); history is kept."""
        self._prompt = system_prompt
        self.messages[0] = self._system_message()

    def clear(self) -> None:
        self.messages = [self._system_message()]

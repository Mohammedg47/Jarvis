"""Conversation state: the message history exchanged with the LLM."""

import re
from collections.abc import Callable, Iterator

from jarvis.core.intents import reply_for
from jarvis.llm.client import ToolCall
from jarvis.memory import MemoryStore
from jarvis.tools.gate import ToolRunner

MAX_TOOL_ROUNDS = 5  # stops a model that keeps calling tools without ever answering
HISTORY_MESSAGES = 20  # how many saved messages are loaded into a new session
HELP_SEARCH_MIN_WORDS = 3  # shorter help-mode messages ("ok", "yes") are not worth a search
HELP_SEARCH_MAX_CHARS = 200
# Words that mean the problem is on the user's screen, so help mode looks at it up front.
SCREEN_WORDS = re.compile(
    r"\b(screen|on my display|this (error|window|page|dialog|message|popup|app)|"
    r"what('s| is) (this|that|happening)|can you see|look at|showing)\b",
    re.IGNORECASE,
)


class Conversation:
    def __init__(
        self,
        chat: Callable[..., Iterator[str | ToolCall]],
        system_prompt: str,
        tools: ToolRunner | None = None,
        memory: MemoryStore | None = None,
        help_prompt: str = "",
        direct: Callable[[str], tuple[str, dict] | None] | None = None,
    ) -> None:
        self._chat = chat
        self._direct = direct  # plain requests answered by calling a tool without the model
        self._help_prompt = help_prompt
        self.help_mode = False
        self._tools = tools
        self._memory = memory
        self._prompt = system_prompt
        self.messages: list[dict] = [self._system_message()]
        if memory is not None:
            self.messages.extend(memory.recent_messages(HISTORY_MESSAGES))

    def _system_message(self) -> dict:
        """The system prompt, plus whatever the user asked Jarvis to remember."""
        content = self._prompt
        if self.help_mode and self._help_prompt:
            content += "\n\n" + self._help_prompt
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
        call = self._direct(text) if self._direct and self._tools is not None else None
        content = text if call else self._with_help_context(text)  # no search for a plain request
        self.messages.append({"role": "user", "content": content})
        try:
            if call is not None:
                reply_text = self._run_direct(*call)
                self._save(start)
                yield reply_text
                return
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
                    self.messages[start]["content"] = text  # save without the search results
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
            self.messages[start]["content"] = text
            self._save(start)
            yield notice
        except BaseException:
            del self.messages[start:]  # drop the unanswered turn, including partial tool steps
            raise

    def _run_direct(self, tool: str, arguments: dict) -> str:
        """Call the tool for a plain request (see core/intents.py), record the exchange and
        return the reply."""
        result = self._tools.run(tool, arguments)
        reply = reply_for(tool, arguments, result)
        self.messages.append(
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": tool, "arguments": arguments}}],
            }
        )
        self.messages.append({"role": "tool", "tool_name": tool, "content": result})
        self.messages.append({"role": "assistant", "content": reply})
        return reply

    def _with_help_context(self, text: str) -> str:
        """In help mode, gather context up front and attach it to the user's message, because a
        small model does not reliably decide to search or look at the screen on its own: a
        description of the screen when the message is about it, and web search results."""
        if not self.help_mode or self._tools is None:
            return text
        parts = [text]
        if self._tools.registry.get("look_at_screen") is not None and SCREEN_WORDS.search(text):
            screen = self._tools.run("look_at_screen", {"question": text[:HELP_SEARCH_MAX_CHARS]})
            if not screen.startswith("Error"):
                parts.append("What is on the user's screen right now:\n" + screen)
        if (
            self._tools.registry.get("web_search") is not None
            and len(text.split()) >= HELP_SEARCH_MIN_WORDS
        ):
            results = self._tools.run("web_search", {"query": text[:HELP_SEARCH_MAX_CHARS]})
            if not results.startswith(("Error", "No results")):
                parts.append("Web search results for this question:\n" + results)
        return "\n\n".join(parts)

    def set_help_mode(self, on: bool) -> None:
        """Turn help mode on or off; history is kept."""
        self.help_mode = on
        self.messages[0] = self._system_message()

    def _stream(self) -> Iterator[str | ToolCall]:
        if self._tools is None:
            return self._chat(self.messages)
        return self._chat(self.messages, tools=self._tools.schemas())

    def set_system_prompt(self, system_prompt: str) -> None:
        """Swap the system prompt (e.g. a personality change); history is kept."""
        self._prompt = system_prompt
        self.messages[0] = self._system_message()

    def clear(self) -> None:
        self.help_mode = False
        self.messages = [self._system_message()]

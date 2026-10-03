"""Terminal chat interface."""

import sys
from collections.abc import Callable

from prompt_toolkit import PromptSession

from jarvis.core.conversation import Conversation
from jarvis.llm.client import LLMError

HELP = "Commands: /clear  forget this conversation, /help  show this, /exit  quit"


def _make_reader() -> Callable[[], str]:
    """Line editing with prompt_toolkit in a real console, plain input() when piped."""
    if sys.stdin.isatty():
        session = PromptSession()
        return lambda: session.prompt("You: ")
    return lambda: input("You: ")


def confirm_in_terminal(name: str, arguments: dict) -> bool:
    """Ask the user to approve a risky tool call. Anything but an explicit yes is a no."""
    args = ", ".join(f"{k}={v!r}" for k, v in arguments.items())
    answer = input(f"\n[confirm] Jarvis wants to run {name}({args}). Allow? [y/N] ")
    return answer.strip().lower() in ("y", "yes")


def run_cli(conversation: Conversation) -> None:
    read = _make_reader()
    print(f"Jarvis is ready. {HELP}")
    while True:
        try:
            text = read().strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not text:
            continue
        if text.startswith("/"):
            command = text.lower()
            if command in ("/exit", "/quit"):
                break
            if command == "/clear":
                conversation.clear()
                print("Conversation cleared.")
            elif command == "/help":
                print(HELP)
            else:
                print(f"Unknown command {text}. {HELP}")
            continue

        print("Jarvis: ", end="", flush=True)
        try:
            for chunk in conversation.send(text):
                print(chunk, end="", flush=True)
        except LLMError as exc:
            print(f"\n[error] {exc}")
        except KeyboardInterrupt:
            print("\n[interrupted]")
        else:
            print()
    print("Goodbye.")

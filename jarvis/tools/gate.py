"""The single permission gate every tool call passes through."""

import inspect
import logging
from collections.abc import Callable
from typing import Any

from jarvis.tools.registry import RISKY, Tool, ToolRegistry

logger = logging.getLogger("jarvis.tools")

# Asked before a risky tool runs: (tool name, arguments) -> approved?
ConfirmFn = Callable[[str, dict], bool]


class ToolRunner:
    """Runs tool calls requested by the LLM. Always returns text for the LLM, never raises."""

    def __init__(self, registry: ToolRegistry, confirm: ConfirmFn | None = None) -> None:
        self.registry = registry
        self.confirm = confirm

    def schemas(self) -> list[dict]:
        return self.registry.schemas()

    def run(self, name: str, arguments: dict | None) -> str:
        arguments = arguments or {}
        tool = self.registry.get(name)
        if tool is None:
            logger.warning("LLM called unknown tool %r", name)
            available = ", ".join(self.registry.names()) or "none"
            return f"Error: there is no tool named '{name}'. Available tools: {available}."

        try:
            arguments = _check_arguments(tool, arguments)
        except ValueError as exc:
            logger.warning("Bad arguments for %s: %s", name, exc)
            return f"Error: {exc}"

        if tool.risk == RISKY and not self._approved(name, arguments):
            logger.info("User declined risky tool %s %s", name, arguments)
            return f"The user declined to run '{name}'. Do not retry it; tell the user it was cancelled."

        try:
            result = tool.func(**arguments)
        except Exception as exc:  # a broken tool must never crash the chat
            logger.exception("Tool %s failed", name)
            return f"Error: '{name}' failed: {exc}"
        logger.info("Tool %s %s -> %.200r", name, arguments, result)
        return "Done." if result is None else str(result)

    def _approved(self, name: str, arguments: dict) -> bool:
        if self.confirm is None:  # no way to ask, so refuse: risky tools fail closed
            return False
        try:
            return bool(self.confirm(name, arguments))
        except (EOFError, KeyboardInterrupt):
            return False


def _check_arguments(tool: Tool, arguments: dict) -> dict:
    """Reject unknown or missing arguments and coerce the number types small models get wrong."""
    params = inspect.signature(tool.func).parameters
    unknown = [a for a in arguments if a not in params]
    if unknown:
        raise ValueError(f"'{tool.name}' has no argument(s) {', '.join(unknown)}")
    missing = [p for p, spec in params.items() if spec.default is spec.empty and p not in arguments]
    if missing:
        raise ValueError(f"'{tool.name}' is missing required argument(s) {', '.join(missing)}")

    properties = tool.parameters["properties"]
    return {key: _coerce(value, properties[key]["type"]) for key, value in arguments.items()}


def _coerce(value: Any, json_type: str) -> Any:
    try:
        if json_type == "integer" and not isinstance(value, bool):
            return int(value)
        if json_type == "number" and not isinstance(value, bool):
            return float(value)
        if json_type == "boolean" and isinstance(value, str):
            return value.strip().lower() in ("true", "yes", "1")
    except (TypeError, ValueError):
        raise ValueError(f"expected {json_type}, got {value!r}") from None
    return value

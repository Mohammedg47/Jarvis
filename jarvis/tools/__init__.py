"""Tools Jarvis can call. Importing this package registers the built-in tools."""

from jarvis.tools import (  # noqa: F401  (registers the tools)
    apps,
    builtin,
    calendar,
    files,
    gmail,
    memory,
    reminders,
    screen,
    system,
    web,
)
from jarvis.tools.gate import ConfirmFn, ToolRunner
from jarvis.tools.registry import RISKY, SAFE, ToolRegistry, default_registry, tool

__all__ = ["RISKY", "SAFE", "ConfirmFn", "ToolRegistry", "ToolRunner", "default_registry", "tool"]

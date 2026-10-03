"""Tool registry: the `@tool` decorator and JSON schema generation from signatures."""

import inspect
import types
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Union, get_args, get_origin, get_type_hints

SAFE = "safe"
RISKY = "risky"

_JSON_TYPES = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    risk: str
    func: Callable[..., Any]
    parameters: dict  # JSON schema for the arguments

    def schema(self) -> dict:
        """The tool definition in the format Ollama expects."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        return [t.schema() for t in self._tools.values()]

    def tool(self, risk: str = SAFE, name: str | None = None) -> Callable:
        """Decorator that registers a function as a tool. The function is returned unchanged."""
        if risk not in (SAFE, RISKY):
            raise ValueError(f"risk must be '{SAFE}' or '{RISKY}', not {risk!r}")

        def decorator(func: Callable) -> Callable:
            self.register(build_tool(func, risk, name))
            return func

        return decorator


def build_tool(func: Callable, risk: str, name: str | None = None) -> Tool:
    description, arg_docs = _parse_docstring(inspect.getdoc(func) or "")
    if not description:
        raise ValueError(f"Tool '{func.__name__}' needs a docstring: the LLM reads it")
    return Tool(
        name=name or func.__name__,
        description=description,
        risk=risk,
        func=func,
        parameters=_parameters_schema(func, arg_docs),
    )


def _parameters_schema(func: Callable, arg_docs: dict[str, str]) -> dict:
    hints = get_type_hints(func)
    properties: dict[str, dict] = {}
    required: list[str] = []
    for pname, param in inspect.signature(func).parameters.items():
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            raise ValueError(f"Tool '{func.__name__}': *args/**kwargs are not supported")
        prop = _type_schema(hints.get(pname, str))
        if pname in arg_docs:
            prop["description"] = arg_docs[pname]
        properties[pname] = prop
        if param.default is param.empty:
            required.append(pname)
    return {"type": "object", "properties": properties, "required": required}


def _type_schema(annotation: Any) -> dict:
    origin = get_origin(annotation)
    if origin is Literal:
        values = list(get_args(annotation))
        return {"type": _JSON_TYPES.get(type(values[0]), "string"), "enum": values}
    if origin in (Union, types.UnionType):  # e.g. `str | None`
        args = [a for a in get_args(annotation) if a is not type(None)]
        return _type_schema(args[0]) if len(args) == 1 else {"type": "string"}
    if origin is not None:  # list[str], dict[str, int], ...
        annotation = origin
    return {"type": _JSON_TYPES.get(annotation, "string")}


def _parse_docstring(doc: str) -> tuple[str, dict[str, str]]:
    """Split a Google-style docstring into its summary and per-argument descriptions."""
    summary_lines: list[str] = []
    arg_docs: dict[str, str] = {}
    in_args = False
    current: str | None = None
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped in ("Args:", "Arguments:"):
            in_args = True
            continue
        if in_args:
            if not stripped:
                continue
            if not line.startswith((" ", "\t")):  # a new unindented section ends Args
                in_args = False
            elif ":" in stripped and stripped.split(":", 1)[0].replace("_", "").isalnum():
                current, text = (s.strip() for s in stripped.split(":", 1))
                arg_docs[current] = text
                continue
            elif current:
                arg_docs[current] += " " + stripped
                continue
        if not in_args:
            summary_lines.append(stripped)
    return " ".join(line for line in summary_lines if line), arg_docs


default_registry = ToolRegistry()
tool = default_registry.tool

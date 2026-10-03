import pytest

from jarvis.core.conversation import MAX_TOOL_ROUNDS, Conversation
from jarvis.llm.client import ToolCall
from jarvis.tools import RISKY, ToolRegistry, ToolRunner, default_registry


def make_registry():
    reg = ToolRegistry()
    calls = []

    @reg.tool()
    def add(a: int, b: int = 1) -> str:
        """Add two numbers.

        Args:
            a: The first number.
            b: The second number.
        """
        return str(a + b)

    @reg.tool(risk=RISKY)
    def wipe(target: str) -> str:
        """Dummy risky tool."""
        calls.append(target)
        return "wiped"

    @reg.tool()
    def broken() -> str:
        """Always fails."""
        raise RuntimeError("kaboom")

    return reg, calls


def test_builtin_get_time_is_registered_as_safe():
    tool = default_registry.get("get_time")
    assert tool is not None and tool.risk == "safe"


def test_schema_comes_from_the_signature():
    reg, _ = make_registry()
    fn = reg.get("add").schema()["function"]
    assert fn["name"] == "add"
    assert fn["description"] == "Add two numbers."
    assert fn["parameters"] == {
        "type": "object",
        "properties": {
            "a": {"type": "integer", "description": "The first number."},
            "b": {"type": "integer", "description": "The second number."},
        },
        "required": ["a"],
    }


def test_tool_needs_a_docstring_and_valid_risk():
    reg = ToolRegistry()
    with pytest.raises(ValueError):
        reg.tool()(lambda: None)
    with pytest.raises(ValueError):
        reg.tool(risk="dangerous")


def test_duplicate_name_is_rejected():
    reg, _ = make_registry()
    with pytest.raises(ValueError):
        reg.tool()(make_registry()[0].get("add").func)


def test_safe_tool_runs_without_asking():
    reg, _ = make_registry()
    runner = ToolRunner(reg, confirm=lambda n, a: pytest.fail("should not ask"))
    assert runner.run("add", {"a": "2", "b": 3}) == "5"  # "2" is coerced to an int


def test_risky_tool_waits_for_approval():
    reg, calls = make_registry()
    asked = []

    def confirm(name, args):
        asked.append((name, args))
        return True

    assert ToolRunner(reg, confirm).run("wipe", {"target": "x"}) == "wiped"
    assert asked == [("wipe", {"target": "x"})] and calls == ["x"]


def test_risky_tool_declined_or_unconfirmable_does_not_run():
    reg, calls = make_registry()
    assert "declined" in ToolRunner(reg, lambda n, a: False).run("wipe", {"target": "x"})
    assert "declined" in ToolRunner(reg, confirm=None).run("wipe", {"target": "x"})
    assert calls == []


def test_errors_are_returned_not_raised():
    reg, _ = make_registry()
    runner = ToolRunner(reg)
    assert "kaboom" in runner.run("broken", {})
    assert "no tool named 'nope'" in runner.run("nope", {})
    assert "missing" in runner.run("add", {})
    assert "no argument" in runner.run("add", {"a": 1, "zzz": 2})
    assert "expected integer" in runner.run("add", {"a": "many"})


def scripted_chat(*rounds):
    """A fake LLM that yields one scripted list of chunks per call."""
    seen = []
    script = iter(rounds)

    def chat(messages, tools=None):
        seen.append((list(messages), tools))
        yield from next(script)

    return chat, seen


def test_tool_loop_feeds_the_result_back_to_the_llm():
    reg, _ = make_registry()
    chat, seen = scripted_chat([ToolCall("add", {"a": 2, "b": 3})], ["It is ", "5."])
    convo = Conversation(chat, "sys", ToolRunner(reg))

    assert "".join(convo.send("2+3?")) == "It is 5."
    assert [m["role"] for m in convo.messages] == [
        "system",
        "user",
        "assistant",
        "tool",
        "assistant",
    ]
    assert convo.messages[3] == {"role": "tool", "tool_name": "add", "content": "5"}
    assert seen[0][1] == reg.schemas()  # the schemas reach the LLM
    assert seen[1][0][-1]["content"] == "5"  # and the result goes back to it


def test_failing_tool_does_not_break_the_conversation():
    reg, _ = make_registry()
    chat, _ = scripted_chat([ToolCall("broken")], ["Sorry, that failed."])
    convo = Conversation(chat, "sys", ToolRunner(reg))
    assert "".join(convo.send("go")) == "Sorry, that failed."
    assert "kaboom" in convo.messages[3]["content"]


def test_endless_tool_calls_are_cut_off():
    reg, _ = make_registry()
    chat, _ = scripted_chat(*[[ToolCall("add", {"a": 1})]] * MAX_TOOL_ROUNDS)
    convo = Conversation(chat, "sys", ToolRunner(reg))
    assert "too many tool steps" in "".join(convo.send("loop"))


def test_failure_mid_tool_loop_drops_the_whole_turn():
    reg, _ = make_registry()

    def chat(messages, tools=None):
        if len(messages) == 2:
            yield ToolCall("add", {"a": 1})
        else:
            raise RuntimeError("boom")

    convo = Conversation(chat, "sys", ToolRunner(reg))
    with pytest.raises(RuntimeError):
        list(convo.send("hi"))
    assert len(convo.messages) == 1

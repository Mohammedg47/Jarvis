import pytest

from jarvis.core import intents
from jarvis.core.conversation import Conversation
from jarvis.tools import ToolRegistry, ToolRunner


@pytest.mark.parametrize(
    "text, expected",
    [
        ("close notepad", ("close_app", "notepad")),
        ("Please close the Notepad app.", ("close_app", "Notepad")),
        ("can you open spotify?", ("open_app", "spotify")),
        ("quit chrome please", ("close_app", "chrome")),
        ("launch file explorer", ("open_app", "file explorer")),
        ("open the file notes from last week please", None),  # too long to be an app name
        ("what does close mean", None),
        ("", None),
    ],
)
def test_match_app_request(text, expected):
    assert intents.match_app_request(text) == expected


def test_direct_call_only_for_apps_that_exist(monkeypatch):
    monkeypatch.setattr("jarvis.tools.apps.is_known_app", lambda name: name == "notepad")
    monkeypatch.setattr("jarvis.tools.apps.is_running", lambda name: name == "zoom")
    assert intents.direct_call("open notepad") == ("open_app", {"name": "notepad"})
    assert intents.direct_call("open zoom") is None
    assert intents.direct_call("close zoom") == ("close_app", {"name": "zoom"})
    assert intents.direct_call("close nothing") is None


def test_declined_and_error_replies_are_plain():
    declined = "The user declined to run 'close_app'. Do not retry it."
    assert intents.reply_for("close_app", {"name": "notepad"}, declined) == (
        "Okay, I did not close notepad."
    )
    assert intents.reply_for("open_app", {}, "Error: I do not know an app.") == (
        "I do not know an app."
    )


def make_runner(approve=True):
    reg = ToolRegistry()
    calls = []

    @reg.tool(risk="risky")
    def close_app(name: str) -> str:
        """Close.

        Args:
            name: App.
        """
        calls.append(name)
        return f"Asked {name} to close."

    return ToolRunner(reg, confirm=lambda n, a: approve), calls


def never_called(messages, tools=None):
    raise AssertionError("the model must not be asked for a plain close request")
    yield


def test_plain_close_request_calls_the_tool_without_the_model():
    runner, calls = make_runner()
    convo = Conversation(
        never_called, "sys", runner, direct=lambda t: ("close_app", {"name": "notepad"})
    )
    assert "".join(convo.send("close notepad")) == "Asked notepad to close."
    assert calls == ["notepad"]
    roles = [m["role"] for m in convo.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]  # tool step is kept


def test_declining_the_confirmation_cancels_without_the_model():
    runner, calls = make_runner(approve=False)
    convo = Conversation(
        never_called, "sys", runner, direct=lambda t: ("close_app", {"name": "notepad"})
    )
    assert "".join(convo.send("close notepad")) == "Okay, I did not close notepad."
    assert calls == []


def test_other_messages_still_go_to_the_model():
    runner, _ = make_runner()

    def chat(messages, tools=None):
        yield "model reply"

    convo = Conversation(chat, "sys", runner, direct=lambda t: None)
    assert "".join(convo.send("hello")) == "model reply"

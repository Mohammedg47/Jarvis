import pytest

from jarvis.core.conversation import Conversation
from jarvis.llm.system_prompt import build_system_prompt


def fake_chat(messages):
    yield "Hi "
    yield f"({len(messages)})"


def test_send_streams_and_records_history():
    convo = Conversation(fake_chat, "sys")
    assert "".join(convo.send("hello")) == "Hi (2)"
    assert "".join(convo.send("again")) == "Hi (4)"
    assert [m["role"] for m in convo.messages] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
    ]


def test_clear_keeps_only_system_prompt():
    convo = Conversation(fake_chat, "sys")
    list(convo.send("hello"))
    convo.clear()
    assert convo.messages == [{"role": "system", "content": "sys"}]


def test_failed_reply_drops_the_user_message():
    def broken(messages):
        raise RuntimeError("boom")
        yield

    convo = Conversation(broken, "sys")
    with pytest.raises(RuntimeError):
        list(convo.send("hello"))
    assert len(convo.messages) == 1


@pytest.mark.parametrize("personality", ["playful", "formal"])
def test_system_prompt_loads_from_disk(personality):
    prompt = build_system_prompt(personality)
    assert "Jarvis" in prompt
    assert f"Personality: {personality}" in prompt


def test_set_system_prompt_keeps_history():
    convo = Conversation(fake_chat, "sys")
    list(convo.send("hello"))
    convo.set_system_prompt("new")
    assert convo.messages[0]["content"] == "new"
    assert len(convo.messages) == 3

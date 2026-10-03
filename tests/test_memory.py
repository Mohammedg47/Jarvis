from pathlib import Path

from jarvis.core.conversation import Conversation
from jarvis.memory import MemoryStore
from jarvis.tools import memory as memory_tools


def fake_chat(messages):
    yield "ok"


def test_database_is_created_on_first_run(tmp_path: Path):
    path = tmp_path / "sub" / "memory.db"
    MemoryStore(path).close()
    assert path.exists()


def test_history_survives_a_restart(tmp_path: Path):
    path = tmp_path / "memory.db"
    store = MemoryStore(path)
    list(Conversation(fake_chat, "sys", memory=store).send("my name is Sam"))
    store.close()

    new_convo = Conversation(fake_chat, "sys", memory=MemoryStore(path))
    assert [m["content"] for m in new_convo.messages[1:]] == ["my name is Sam", "ok"]


def test_only_recent_messages_are_loaded():
    store = MemoryStore(Path(":memory:"))
    for i in range(30):
        store.add_message("user", str(i))
    assert [m["content"] for m in store.recent_messages(3)] == ["27", "28", "29"]


def test_failed_turn_is_not_saved():
    def broken(messages):
        raise RuntimeError("boom")
        yield

    store = MemoryStore(Path(":memory:"))
    try:
        list(Conversation(broken, "sys", memory=store).send("hi"))
    except RuntimeError:
        pass
    assert store.recent_messages(10) == []


def test_preferences_are_recalled_and_injected_in_prompt():
    store = MemoryStore(Path(":memory:"))
    memory_tools.configure(store)
    convo = Conversation(fake_chat, "sys", memory=store)
    assert "Remembered" in memory_tools.remember_preference("Theme", "dark mode")
    assert "theme: dark mode" in memory_tools.recall_preferences()
    list(convo.send("hello"))
    assert "theme: dark mode" in convo.messages[0]["content"]
    memory_tools.configure(None)


def test_forget_all_clears_everything():
    store = MemoryStore(Path(":memory:"))
    store.add_message("user", "hi")
    store.set_preference("a", "b")
    store.forget_all()
    assert store.recent_messages(10) == [] and store.preferences() == {}


def test_turns_that_used_tools_are_not_replayed():
    store = MemoryStore(Path(":memory:"))
    store.add_message("user", "hi")
    store.add_message("assistant", "hello")
    store.add_message("user", "open notepad", used_tools=True)
    store.add_message("assistant", "Notepad opened.", used_tools=True)
    assert [m["content"] for m in store.recent_messages(10)] == ["hi", "hello"]

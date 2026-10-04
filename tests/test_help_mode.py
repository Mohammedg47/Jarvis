from jarvis.core.conversation import Conversation
from jarvis.llm.system_prompt import build_help_prompt
from jarvis.memory import MemoryStore
from jarvis.tools import ToolRegistry, ToolRunner


def make_runner(results):
    reg = ToolRegistry()

    @reg.tool()
    def web_search(query: str) -> str:
        """Search.

        Args:
            query: What to search for.
        """
        results.append(query)
        return "[1] Title\nhttps://example.com\nsnippet"

    return ToolRunner(reg)


def echo_chat(messages, tools=None):
    yield messages[-1]["content"]


def test_help_prompt_is_added_only_in_help_mode():
    convo = Conversation(echo_chat, "sys", help_prompt="HELP")
    assert convo.messages[0]["content"] == "sys"
    convo.set_help_mode(True)
    assert convo.messages[0]["content"] == "sys\n\nHELP"
    convo.set_help_mode(False)
    assert convo.messages[0]["content"] == "sys"


def test_help_prompt_file_asks_for_steps():
    assert "numbered steps" in build_help_prompt()


def test_help_mode_searches_automatically_and_attaches_results():
    searched = []
    convo = Conversation(echo_chat, "sys", make_runner(searched), help_prompt="HELP")
    convo.set_help_mode(True)
    reply = "".join(convo.send("how do I reset my wifi adapter"))
    assert searched == ["how do I reset my wifi adapter"]
    assert "https://example.com" in reply


def test_no_search_outside_help_mode_or_for_short_messages():
    searched = []
    convo = Conversation(echo_chat, "sys", make_runner(searched), help_prompt="HELP")
    list(convo.send("how do I reset my wifi adapter"))
    convo.set_help_mode(True)
    list(convo.send("ok thanks"))
    assert searched == []


def test_saved_history_has_the_question_without_search_results(tmp_path):
    store = MemoryStore(tmp_path / "m.db")
    convo = Conversation(echo_chat, "sys", make_runner([]), store, help_prompt="HELP")
    convo.set_help_mode(True)
    list(convo.send("how do I reset my wifi adapter"))
    assert store.recent_messages(5)[0]["content"] == "how do I reset my wifi adapter"
    store.close()


def test_clear_leaves_help_mode():
    convo = Conversation(echo_chat, "sys", help_prompt="HELP")
    convo.set_help_mode(True)
    convo.clear()
    assert not convo.help_mode
    assert convo.messages[0]["content"] == "sys"


def test_help_mode_looks_at_the_screen_when_the_message_is_about_it():
    reg = ToolRegistry()
    seen = []

    @reg.tool()
    def look_at_screen(question: str = "") -> str:
        """Look.

        Args:
            question: What to find out.
        """
        seen.append(question)
        return "An Excel window with a #REF! error."

    convo = Conversation(echo_chat, "sys", ToolRunner(reg), help_prompt="HELP")
    convo.set_help_mode(True)
    reply = "".join(convo.send("I'm stuck, what does this error mean"))
    assert seen and "#REF!" in reply
    list(convo.send("thanks"))
    assert len(seen) == 1

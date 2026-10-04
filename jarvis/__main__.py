from jarvis.core.config import get_settings
from jarvis.core.conversation import Conversation
from jarvis.core.events import EventBus, log_state
from jarvis.core.logging import setup_logging
from jarvis.core.personality import PersonalityControl
from jarvis.google import service as google_service
from jarvis.google.alerts import AlertPoller
from jarvis.llm.client import OllamaClient
from jarvis.llm.system_prompt import build_system_prompt
from jarvis.memory import MemoryStore
from jarvis.tools import ToolRunner, default_registry, reminders
from jarvis.tools.memory import configure as configure_memory_tools
from jarvis.ui.cli import Reader, make_confirm, run_cli
from jarvis.voice.elevenlabs_io import Voice
from jarvis.voice.session import VoiceSession


def start_voice(settings, reader: Reader, bus: EventBus) -> VoiceSession | None:
    """Voice needs an ElevenLabs key and a real console; otherwise Jarvis stays text-only."""
    if not settings.elevenlabs_api_key:
        print("Voice is off: set ELEVENLABS_API_KEY in .env to enable it.")
        return None
    if not reader.interactive:
        return None
    session = VoiceSession(
        Voice(settings.elevenlabs_api_key, settings.elevenlabs_voice_id),
        settings.push_to_talk_hotkey,
        reader.inject,
        speak_replies=settings.speak_replies,
        bus=bus,
        stop_hotkey=settings.stop_hotkey,
    )
    return session if session.start() else None


def main() -> None:
    settings = get_settings()
    logger = setup_logging(settings)
    logger.info(
        "Jarvis starting (model=%s, personality=%s)", settings.ollama_model, settings.personality
    )
    client = OllamaClient(settings.ollama_model)
    memory = MemoryStore(settings.data_dir / "memory.db")
    configure_memory_tools(memory)
    bus = EventBus()
    bus.subscribe(log_state)
    reader = Reader()
    voice = start_voice(settings, reader, bus)

    def alert(message: str) -> None:
        print(f"\n[reminder] {message}")
        if voice is not None:
            voice.say(f"Reminder: {message}")

    reminders.start(memory, alert)
    google_service.configure(settings)
    poller = AlertPoller(settings, alert)
    started = poller.start()
    if started:
        print(f"Google alerts on: {', '.join(started)}.")
    runner = ToolRunner(default_registry, confirm=make_confirm(reader, voice))
    conversation = Conversation(
        client.chat, build_system_prompt(settings.personality), runner, memory
    )

    personality = PersonalityControl(settings.personality)
    personality.subscribe(lambda name: conversation.set_system_prompt(build_system_prompt(name)))

    def set_muted(muted: bool) -> None:
        voice.speak_replies = not muted
        if muted:
            voice.stop_speaking()

    def chat(show_reply=None) -> None:
        run_cli(conversation, memory, reader, voice, personality, bus, show_reply)

    try:
        if settings.show_character and reader.interactive:
            from jarvis.ui.app import run_character  # Qt is only loaded when shown
            from jarvis.ui.tray import TrayControls

            controls = TrayControls(personality=personality)
            if voice is not None:
                controls = TrayControls(lambda: not voice.speak_replies, set_muted, personality)
            run_character(
                chat,
                lambda text: reader.inject(text, "overlay"),
                bus,
                settings.data_dir / "character.json",
                settings.character_roam,
                controls,
            )
        else:
            chat()
    finally:
        reminders.stop()
        poller.stop()
        if voice is not None:
            voice.stop()
        memory.close()


if __name__ == "__main__":
    main()

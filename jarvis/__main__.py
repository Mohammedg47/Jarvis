import argparse
import os
import sys

from jarvis.core import autostart
from jarvis.core.assistant import Assistant
from jarvis.core.config import get_settings
from jarvis.core.conversation import Conversation
from jarvis.core.events import EventBus, Notifier, log_state
from jarvis.core.intents import direct_call
from jarvis.core.logging import setup_logging
from jarvis.core.personality import PersonalityControl
from jarvis.google import service as google_service
from jarvis.google.alerts import AlertPoller
from jarvis.llm.client import OllamaClient
from jarvis.llm.system_prompt import build_help_prompt, build_system_prompt
from jarvis.memory import MemoryStore
from jarvis.tools import ToolRunner, default_registry, reminders
from jarvis.tools.memory import configure as configure_memory_tools
from jarvis.ui.cli import Reader, make_confirm, run_cli
from jarvis.voice.elevenlabs_io import Voice
from jarvis.voice.hotkey import PressHotkey
from jarvis.voice.session import VoiceSession


def start_voice(settings, reader: Reader, bus: EventBus, windowed: bool) -> VoiceSession | None:
    """Voice needs an ElevenLabs key and either the Qt app or a real console; otherwise Jarvis
    stays text-only."""
    if not settings.elevenlabs_api_key:
        print("Voice is off: set ELEVENLABS_API_KEY in .env to enable it.")
        return None
    if not (windowed or reader.interactive):
        return None
    session = VoiceSession(
        Voice(settings.elevenlabs_api_key, settings.elevenlabs_voice_id),
        settings.push_to_talk_hotkey,
        reader.inject,
        speak_replies=settings.speak_replies,
        bus=bus,
        stop_hotkey=settings.stop_hotkey,
        wake_dir=settings.data_dir / "wakeword",
        wake_threshold=settings.wake_threshold,
    )
    if not session.start():
        return None
    if settings.wake_word and session.set_wake_word(True):
        print('Say "Hey Jarvis" to talk hands-free (/wake off to disable).')
    return session


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="jarvis", description="Jarvis, your laptop assistant.")
    parser.add_argument(
        "--cli",
        action="store_true",
        help="terminal chat only (no windows): the debug / secondary interface",
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="start quietly in the tray (the character shows, the chat window stays closed)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    if sys.stdout is None:  # a windowed launch (login, double-click) has no console
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    windowed = not args.cli
    settings = get_settings()
    logger = setup_logging(settings)
    logger.info(
        "Jarvis starting (model=%s, personality=%s, %s)",
        settings.ollama_model,
        settings.personality,
        "terminal" if args.cli else "Qt app",
    )
    client = OllamaClient(settings.ollama_model)
    memory = MemoryStore(settings.data_dir / "memory.db")
    configure_memory_tools(memory)
    bus = EventBus()
    bus.subscribe(log_state)
    reader = Reader(windowed=windowed)
    surface = None
    if windowed:
        from jarvis.ui.chat import QtSurface  # Qt is only loaded for the windowed app

        surface = QtSurface(reader)
    voice = start_voice(settings, reader, bus, windowed)
    notifier = Notifier()

    def alert(message: str) -> None:
        print(f"\n[reminder] {message}")
        notifier.notify(message)
        if voice is not None:
            voice.say(f"Reminder: {message}")

    reminders.start(memory, alert)
    google_service.configure(settings)
    poller = AlertPoller(settings, alert)
    started = poller.start()
    if started:
        print(f"Google alerts on: {', '.join(started)}.")
    if surface is not None:
        from jarvis.ui.confirm import describe

        confirm = make_confirm(
            reader,
            voice,
            show=lambda name, arguments: surface.question_asked.emit(
                f"Jarvis wants to run: {describe(name, arguments)}"
            ),
            hide=surface.question_closed.emit,
        )
    else:
        confirm = make_confirm(reader, voice)
    runner = ToolRunner(default_registry, confirm=confirm)
    conversation = Conversation(
        client.chat,
        build_system_prompt(settings.personality),
        runner,
        memory,
        help_prompt=build_help_prompt(),
        direct=direct_call,
    )

    personality = PersonalityControl(settings.personality)
    personality.subscribe(lambda name: conversation.set_system_prompt(build_system_prompt(name)))
    assistant = Assistant(conversation, memory, voice, personality, bus)

    def set_muted(muted: bool) -> None:
        voice.speak_replies = not muted
        if muted:
            voice.stop_speaking()

    help_key = None
    try:
        if windowed:
            from jarvis.ui.app import run_app
            from jarvis.ui.tray import TrayControls

            extras = {"is_autostart": autostart.is_enabled, "set_autostart": autostart.set_enabled}
            controls = TrayControls(personality=personality, **extras)
            if voice is not None:
                controls = TrayControls(
                    **extras,
                    is_muted=lambda: not voice.speak_replies,
                    set_muted=set_muted,
                    personality=personality,
                    is_wake_on=lambda: voice.wake_enabled,
                    set_wake=voice.set_wake_word,
                )
            run_app(
                assistant,
                reader,
                surface,
                bus,
                notifier,
                controls,
                settings.data_dir / "character.json",
                settings.character_roam,
                settings.help_hotkey,
                settings.show_character,
                open_chat=not args.background,
                character_style=settings.character_style,
            )
        else:
            if settings.help_hotkey and reader.interactive:
                help_key = PressHotkey(
                    settings.help_hotkey, lambda: reader.inject("/stuck", "hotkey")
                )
                try:
                    help_key.start()
                except Exception:
                    logger.exception("Could not install the help hotkey")
                    help_key = None
            run_cli(conversation, memory, reader, voice, personality, bus)
    finally:
        if help_key is not None:
            help_key.stop()
        reminders.stop()
        poller.stop()
        if voice is not None:
            voice.stop()
        memory.close()


if __name__ == "__main__":
    main()

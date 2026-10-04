# Tech Stack

## Platform
- Windows 11, Python 3.11+.
- Dependencies managed with `pyproject.toml` in a local virtual environment (`.venv`).

## Components
| Area | Choice | Notes |
|---|---|---|
| LLM | Ollama (local) via the `ollama` Python client | Model name set in config. Default `qwen2.5:3b` (benchmarked on the dev laptop: i7-7700HQ, 15.8 GB RAM, GTX 1050 4 GB; 100% on GPU, ~21 tok/s, correct tool calls). 7-8B models exceed 4 GB VRAM and run slowly |
| Text-to-speech | ElevenLabs SDK | Voice ID configurable |
| Speech-to-text | ElevenLabs SDK | Fed by recorded microphone audio |
| Audio capture/playback | `sounddevice`, `numpy` | Push-to-talk recording, playback of TTS audio |
| Hotkey | `keyboard` | Push-to-talk, stop-speaking and help hotkeys |
| App control | `psutil`, `subprocess`, `pywin32` | Open, close and list applications |
| File operations | `pathlib`, `shutil`, `send2trash` | Deletes go to the Recycle Bin |
| System control | `pycaw` (volume), `ctypes` (lock) | Windows APIs |
| Web search | `ddgs` | No API key needed |
| Reminders/timers | `APScheduler` | Fires a spoken/text alert |
| Email/calendar | `google-api-python-client`, `google-auth-oauthlib` | Gmail + Google Calendar via OAuth; tokens stored locally (gitignored), minimal scopes |
| Proactive alerts | `APScheduler` polling jobs | Upcoming events and new important email; poll interval configurable |
| Memory | `sqlite3` (stdlib) | Conversation history and preferences in a local DB file |
| Config | `pydantic-settings` + `.env` | `ELEVENLABS_API_KEY`, model, voice, hotkey, personality |
| CLI | `prompt_toolkit` | Debug / secondary text interface (`--cli`), streaming output |
| Main interface and character | `PySide6` (Qt) | Chat window, Yes/No popup, alert bubbles, system tray; transparent always-on-top character showing premade Noto animated emoji GIFs (CC BY 4.0), with a code-drawn fallback |
| Wake word | `openWakeWord` + `onnxruntime` | Local "Hey Jarvis" model; audio never leaves the laptop until it triggers; models download to the data dir on first use |
| Screenshots and vision | `mss`, `pillow`, Ollama `qwen2.5vl:3b` | Local screen description for help mode (`JARVIS_VISION_MODEL`) |
| Packaging | `PyInstaller`, Inno Setup | Per-user installer with a Startup shortcut. The unsigned exe is flagged by Windows Defender as a false positive, so it needs an exclusion or a code-signing certificate; running from source also works |
| Testing | `pytest` | Tools tested with mocks for the OS and network |
| Lint/format | `ruff` | |

## Architecture
```
jarvis/
  core/     config, logging, main loop, event bus
  llm/      Ollama client, prompts, tool-call loop
  tools/    registry + one module per tool (apps, files, system, web, reminders)
  voice/    microphone, STT, TTS, hotkeys, wake word
  memory/   SQLite store
  ui/       Qt app (chat window, popups, character, tray), CLI
tests/
specs/
```

### Key design rules
- **Tool registry**: each tool is a decorated function with a name, description, JSON schema and a `risk` level (`safe` or `risky`). The LLM only sees registered tools.
- **Permission layer**: every tool call passes through one gate. `risky` tools require a yes/no confirmation, by text or by voice, before running.
- **Event bus**: the core emits state events (idle, listening, thinking, speaking). The character, tray and CLI subscribe to them. A `Notifier` broadcasts alerts (reminders, calendar, email) to every interface.
- **One conversation, many inputs**: text and voice both feed the same message pipeline.
- **UI direction**: the Qt app is the main interface (Qt on the main thread, the assistant loop on a worker thread); `python -m jarvis --cli` keeps the terminal for debugging. Every interface implements a `Surface` and feeds lines to one `Assistant` (slash commands and the reply loop in `core/assistant.py`), so a command works the same everywhere. Conversation, tools and confirmations stay UI-independent (the event bus and `confirm` callback).
- **Direct requests**: plain "open X" / "close X" are answered by calling the tool directly (`core/intents.py`), because the small local model sometimes claims success without calling it. They still pass the permission gate.
- **Personality**: a Playful/Formal setting changes the system prompt and the character's behavior.

## Secrets and data
- `.env` holds `ELEVENLABS_API_KEY`. It is gitignored.
- Google OAuth client credentials and tokens (`credentials.json`, `token.json`) are gitignored. Email send and calendar write tools are `risky`.
- Memory DB and logs live in a local data directory (gitignored).

## Risks to watch
- Small local models can call tools unreliably, so the permission layer and strict schemas are essential.
- ElevenLabs is a cloud service, so voice requires internet and has usage costs.
- Global hotkeys and screen overlays may need elevated permissions in some apps.

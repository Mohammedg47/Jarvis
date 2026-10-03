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
| Hotkey | `keyboard` | Push-to-talk first; wake word later |
| App control | `psutil`, `subprocess`, `pywin32` | Open, close and list applications |
| File operations | `pathlib`, `shutil`, `send2trash` | Deletes go to the Recycle Bin |
| System control | `pycaw` (volume), `ctypes` (lock) | Windows APIs |
| Web search | `ddgs` | No API key needed |
| Reminders/timers | `APScheduler` | Fires a spoken/text alert |
| Email/calendar | `google-api-python-client`, `google-auth-oauthlib` | Gmail + Google Calendar via OAuth; tokens stored locally (gitignored), minimal scopes |
| Proactive alerts | `APScheduler` polling jobs | Upcoming events and new important email; poll interval configurable |
| Memory | `sqlite3` (stdlib) | Conversation history and preferences in a local DB file |
| Config | `pydantic-settings` + `.env` | `ELEVENLABS_API_KEY`, model, voice, hotkey, personality |
| CLI | `prompt_toolkit` + `rich` | Text interface, streaming output |
| Floating character | `PySide6` (Qt) | Transparent, frameless, always-on-top window; system tray icon |
| Testing | `pytest` | Tools tested with mocks for the OS and network |
| Lint/format | `ruff` | |

## Architecture
```
jarvis/
  core/     config, logging, main loop, event bus
  llm/      Ollama client, prompts, tool-call loop
  tools/    registry + one module per tool (apps, files, system, web, reminders)
  voice/    microphone, STT, TTS, hotkey
  memory/   SQLite store
  ui/       CLI, floating character, tray
tests/
specs/
```

### Key design rules
- **Tool registry**: each tool is a decorated function with a name, description, JSON schema and a `risk` level (`safe` or `risky`). The LLM only sees registered tools.
- **Permission layer**: every tool call passes through one gate. `risky` tools require a yes/no confirmation, by text or by voice, before running.
- **Event bus**: the core emits state events (idle, listening, thinking, speaking). The floating character and CLI subscribe to them.
- **One conversation, many inputs**: text and voice both feed the same message pipeline.
- **Personality**: a Playful/Formal setting changes the system prompt and the character's behavior.

## Secrets and data
- `.env` holds `ELEVENLABS_API_KEY`. It is gitignored.
- Google OAuth client credentials and tokens (`credentials.json`, `token.json`) are gitignored. Email send and calendar write tools are `risky`.
- Memory DB and logs live in a local data directory (gitignored).

## Risks to watch
- Small local models can call tools unreliably, so the permission layer and strict schemas are essential.
- ElevenLabs is a cloud service, so voice requires internet and has usage costs.
- Global hotkeys and screen overlays may need elevated permissions in some apps.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Jarvis is an AI assistant that lives on a Windows laptop: voice (ElevenLabs STT/TTS) and text chat, a local Ollama LLM, and admin-like tools (open/close apps, files, system control, web search, reminders, Google email/calendar). See `README.md` for the client brief.

**`specs/` is the source of truth.** Read these before making design decisions:
- `specs/mission.md` - purpose, principles, scope
- `specs/techstack.md` - technology choices and architecture
- `specs/roadmap.md` - phased, checkbox-tracked implementation steps. Tick a step off when it is done.

## Commands

Python 3.12 on Windows (the project requires >=3.11,<3.14; Python 3.14 is also installed but not used).

```powershell
py -3.12 -m venv .venv                      # create the virtual environment (once)
.venv\Scripts\python -m pip install -e ".[dev]"   # install the project and dev tools
.venv\Scripts\python -m jarvis              # run Jarvis
.venv\Scripts\python -m pytest              # run all tests
.venv\Scripts\python -m pytest tests/test_config.py::test_logging_writes_to_file   # run a single test
.venv\Scripts\python -m ruff check .        # lint
.venv\Scripts\python -m ruff format .       # format
```

## Architecture

Package `jarvis/` with submodules `core` (config, logging, main loop), `llm`, `tools`, `voice`, `memory`, `ui`. All submodules have code, plus `google`.

- **Config** (`jarvis/core/config.py`): `get_settings()` returns a pydantic `Settings` loaded from environment variables and a local `.env` (copy `.env.example`). Variables use the `JARVIS_` prefix, except `ELEVENLABS_API_KEY`.
- **Logging** (`jarvis/core/logging.py`): `setup_logging(settings)` logs to the console and a rotating file.
- **LLM** (`jarvis/llm/`): `OllamaClient.chat(messages)` streams reply chunks from the local model; `build_system_prompt(personality)` assembles the prompt from `jarvis/llm/prompts/*.md` (edit those files to change behavior). Errors surface as `LLMError`.
- **Conversation** (`jarvis/core/conversation.py`): holds message history and streams replies; independent of the UI so voice and text can share it. With a `ToolRunner` it also runs the tool-call loop (model calls a tool, result goes back as a `tool` message, up to `MAX_TOOL_ROUNDS`). `OllamaClient.chat(messages, tools)` yields text chunks and `ToolCall` objects.
- **Tools** (`jarvis/tools/`): `@tool(risk="safe"|"risky")` registers a function in `default_registry` (`registry.py`); the JSON schema comes from type hints and the Google-style docstring (the docstring is required, the LLM reads it). `ToolRunner` (`gate.py`) is the single permission gate: it validates arguments, asks the injected `confirm(name, args)` callback before any `risky` tool (no callback means refuse), and turns unknown tools and exceptions into error text for the LLM instead of raising. Built-in tools live in `builtin.py`; add new tool modules and import them in `tools/__init__.py` so they register. The CLI's confirmation is `confirm_in_terminal`; voice will supply its own in Phase 6.
- **Admin tools** (Phase 4): `tools/apps.py` (`open_app` uses a built-in name map + `JARVIS_APPS` JSON overrides, then a Start Menu shortcut search; `list_apps` = apps with visible windows; `close_app` is risky, uses `taskkill` without `/F`, and refuses protected processes), `tools/files.py` (search/open/create/move/delete, plus `write_note` = create a .txt and open it in Notepad, since Jarvis cannot type into other apps; all paths are confined to `allowed_roots()` = standard user folders or `JARVIS_FILE_ROOTS`; create/move never overwrite; `delete_file` is risky and uses the Recycle Bin via send2trash), `tools/system.py` (`set_volume`/`mute` via pycaw, `lock_screen`, risky `shutdown` with a 30 s delay).
- **Memory** (Phase 5): `MemoryStore` (`jarvis/memory/store.py`) is a SQLite DB at `<data dir>\memory.db` with `messages` and `preferences` tables. `Conversation(..., memory=store)` loads the last `HISTORY_MESSAGES` (20) user/assistant messages at startup, saves each finished turn (tool steps are not saved), and appends saved preferences to the system prompt every turn. `tools/memory.py` has `remember_preference` / `recall_preferences` (store injected via `configure()` in `__main__`).
- **Voice** (Phase 6, `jarvis/voice/`): `Voice` (`elevenlabs_io.py`) speaks text (TTS `pcm_24000`, played with sounddevice) and transcribes audio (STT `scribe_v1`); `Recorder` (`audio.py`) records 16 kHz mono from the mic; `PushToTalk`/`HoldTracker` (`hotkey.py`) is the global hold-to-talk hotkey (`keyboard` lib, default ctrl+space); `VoiceSession` (`session.py`) ties them together, sends transcripts to the CLI like typed text and reports every failure through `notify` instead of raising (`VoiceError` messages come from `errors.explain`). Voice is only started with an `ELEVENLABS_API_KEY` and a real console. `JARVIS_SPEAK_REPLIES` (default true) / `/speak [on|off]`, `/stop` toggle spoken replies. Smoke test: `python -m jarvis.voice [say [text] | record | listen]`.
- **Floating character** (Phase 9, `jarvis/ui/`): `character.py` is the frameless, transparent, always-on-top emoji window (`SKIN` maps each `State` to an emoji; drag to move, position saved to `<data dir>\character.json`; optional idle roaming via `JARVIS_CHARACTER_ROAM`). `tray.py` is the system tray icon (Mute spoken replies, Personality submenu, Wander, Quit; the icon follows the state). Personality lives in `PersonalityControl` (`core/personality.py`): `/personality` and the tray both call `set()`, subscribers swap the LLM system prompt (wired in `__main__`) and the character's skin (`SKINS[personality][state]`; formal uses 😐 🧐 🗣️). `popup.py` is the click-to-type box: clicking the character (a press without a drag) opens it, Enter sends the line through `Reader.inject(text, "overlay")` exactly like a voice transcript, and `run_cli(on_reply=...)` shows the reply in the box (so risky-tool confirmations still happen in the terminal or by voice). `app.py` `run_character` runs Qt on the main thread and the CLI loop on a worker thread; `JARVIS_SHOW_CHARACTER=false` gives the terminal-only mode. Bus events reach Qt through the `state_changed` signal.
- **Stopping speech** (Phase 9): replies are spoken with `VoiceSession.say_async` so the prompt stays free. `stop_speaking()` cancels playback and audio still being generated (a speech id is checked before play) and returns the state to idle. It is triggered by the `JARVIS_STOP_HOTKEY` global hotkey (default `esc`, empty disables), `/stop`, any new typed or spoken message, or pressing push-to-talk.
- **Web search and reminders** (Phase 7): `tools/web.py` `web_search` (ddgs, top 5 results, snippets cut to 300 chars; the system prompt tells the LLM to answer briefly and name sources). `tools/reminders.py` uses APScheduler: `set_timer` (in-memory) and `set_reminder` (local `YYYY-MM-DD HH:MM` or `HH:MM`, saved in the `reminders` table of `memory.db`, re-armed by `reminders.start(store, alert)` at startup; overdue ones fire immediately). `alert` in `__main__` prints `[reminder] ...` and speaks it. `/forget` does not delete reminders.
- **Google email and calendar** (Phase 8, `jarvis/google/`, setup in `docs/google-setup.md`): `auth.py` does the OAuth login (scopes `calendar.events`, `gmail.readonly`, `gmail.compose`); `credentials.json` and `token.json` live in the data dir (`JARVIS_GOOGLE_CREDENTIALS` overrides the first). Sign in or re-sign in with `python -m jarvis.google` (while the Google app is in Testing mode the token expires every 7 days). Tools (`tools/calendar.py`, `tools/gmail.py`) never open the browser; the `@google_tool` decorator in `service.py` turns Google errors into error text. `list_events`, `read_emails`, `summarize_email` (returns the text; the LLM summarizes), `draft_email` are safe; `create_event`, `edit_event`, `send_email` are risky. `AlertPoller` (`alerts.py`) polls in the background for events starting within `JARVIS_ALERT_EVENT_MINUTES` and new unread mail with the `JARVIS_ALERT_EMAIL_LABEL` label (default IMPORTANT); `JARVIS_ALERT_EVENTS` / `JARVIS_ALERT_IMPORTANT_EMAIL` turn each off. Alerts go through the same `alert` callback as reminders.
- **Event bus** (Phase 9, `jarvis/core/events.py`): `EventBus.emit(State)` / `subscribe(cb)` with `State` = idle/listening/thinking/speaking; repeats are dropped, safe from any thread. `VoiceSession` emits listening/thinking/speaking, `run_cli` emits thinking/idle, `__main__` subscribes `log_state` (logs `state: ...`). The floating character will subscribe too.
- **CLI** (`jarvis/ui/cli.py`): `Reader` is the single input source (typed line or injected voice transcript); `make_confirm(reader, voice)` confirms risky tools by typing or saying yes/no (`is_yes`). Terminal chat loop with `/speak`, `/personality [playful|formal]` (swaps the system prompt live), `/clear` (live chat only), `/forget` (confirms, then wipes the DB), `/help`, `/exit`. Uses prompt_toolkit in a real console and plain `input()` when stdin is piped.
- **Ollama setup**: install Ollama (`winget install Ollama.Ollama`) and run `ollama pull qwen2.5:3b`. This model was benchmarked on the dev laptop (GTX 1050, 4 GB VRAM) to run fully on the GPU; 7-8B models do not fit. Change it with `JARVIS_OLLAMA_MODEL`.
- **Data directory**: `%APPDATA%\Jarvis` by default (override with `JARVIS_DATA_DIR`). Logs and, later, the memory database live here, outside the repo.

Design rules (see `specs/techstack.md`): tools are registered in a registry with a `safe`/`risky` level; every tool call passes one permission gate, and risky actions need user confirmation.

## Notes

- Development is on Windows (PowerShell primary, Git Bash available).
- Default branch is `main`.
- Never commit `.env`, `credentials.json` or `token.json`.

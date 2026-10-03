# Roadmap

Each phase leaves a working system. Each step is small and has a "done when" check.

## Phase 1: Foundation
- [x] 1. Create the package layout (`jarvis/`, `tests/`) and `pyproject.toml`. *Done when:* `pip install -e .` succeeds.
- [x] 2. Add `.gitignore` (`.venv`, `.env`, data dir). *Done when:* secrets cannot be committed.
- [x] 3. Add config loading (`pydantic-settings`, `.env.example`). *Done when:* settings load from `.env`.
- [x] 4. Add logging to a file and the console. *Done when:* a log line appears in both.
- [x] 5. Set up `pytest` and `ruff` with one passing test. *Done when:* `pytest` and `ruff check` pass.
- [x] 6. Update `CLAUDE.md` with the real commands. *Done when:* install, run and test commands are documented.

## Phase 2: Text brain (CLI)
- [x] 1. Install Ollama and pull the default model (`qwen2.5:3b`); document it. *Done when:* `ollama run` works.
- [x] 2. Write an Ollama client wrapper that takes a model name from config. *Done when:* it returns a reply to "hello".
- [x] 3. Add a system prompt file. *Done when:* the prompt is loaded from disk.
- [x] 4. Build a CLI chat loop with message history. *Done when:* a multi-turn chat works in the terminal.
- [x] 5. Stream replies token by token. *Done when:* text appears as it is generated.
- [x] 6. Add `/exit` and `/clear` commands. *Done when:* both work.

## Phase 3: Tool framework and safety
- [x] 1. Create the tool registry and `@tool` decorator with a risk level. *Done when:* a sample tool is registered.
- [x] 2. Generate JSON schemas from tool signatures. *Done when:* the schema is passed to Ollama.
- [x] 3. Implement the tool-call loop (LLM calls tool, result goes back to the LLM). *Done when:* a `get_time` tool answers "what time is it?".
- [x] 4. Add the permission gate with a yes/no confirmation for `risky` tools. *Done when:* a dummy risky tool waits for approval.
- [x] 5. Handle tool errors and unknown tools gracefully. *Done when:* a failing tool does not crash the chat.

## Phase 4: Admin tools
- [x] 1. `open_app`: launch by name from an allow-list/config map. *Done when:* "open Notepad" works.
- [x] 2. `list_apps`: list running apps. *Done when:* it returns process names.
- [x] 3. `close_app` (risky): close by name after confirmation. *Done when:* Notepad closes only after "yes".
- [x] 4. `search_files`: find files by name in chosen folders. *Done when:* a known file is found.
- [x] 5. `open_file`: open a file with its default app. *Done when:* a text file opens.
- [x] 6. `create_file`, `move_file`: basic file writes. *Done when:* both work in a temp folder test.
- [x] 7. `delete_file` (risky): sends to the Recycle Bin. *Done when:* the file is recoverable and confirmation was required.
- [x] 8. `set_volume` and `mute`. *Done when:* system volume changes.
- [x] 9. `lock_screen` and `shutdown` (risky). *Done when:* lock works and shutdown requires confirmation.

## Phase 5: Memory
- [x] 1. Create the SQLite schema (messages, preferences). *Done when:* the DB file is created on first run.
- [x] 2. Save every message. *Done when:* history survives a restart.
- [x] 3. Load recent history into the next session. *Done when:* Jarvis recalls the last conversation.
- [x] 4. Add `remember_preference` and `recall_preferences` tools. *Done when:* "I prefer dark mode" is recalled later.
- [x] 5. Add a `/forget` command to wipe memory. *Done when:* the DB is cleared on request.

## Phase 6: Voice
- [x] 1. Add ElevenLabs key check and a TTS function. *Done when:* a test sentence is spoken.
- [x] 2. Speak Jarvis's replies (toggle in config). *Done when:* text replies are also spoken.
- [ ] 3. Record microphone audio to a buffer. *Done when:* a saved clip plays back. *(Pending live check: `python -m jarvis.voice record` ran without errors but playback was not heard; likely the default mic is the Beats headset. Retest later, try another input device.)*
- [x] 4. Send audio to ElevenLabs STT. *Done when:* the transcript matches what was said.
- [x] 5. Add the push-to-talk hotkey (hold to record, release to send). *Done when:* hold, speak and get a spoken answer.
- [x] 6. Merge voice and text into one input pipeline. *Done when:* both work in the same session.
- [x] 7. Voice confirmations for risky actions. *Done when:* saying "yes" or "no" approves or cancels.
- [x] 8. Handle errors (no mic, no internet, API failure) with a clear message. *Done when:* each failure is reported without a crash.

## Phase 7: Web search and reminders
- [x] 1. `web_search` tool using `ddgs`. *Done when:* it returns top results.
- [x] 2. Summarize results into a short answer with sources. *Done when:* a factual question gets a sourced answer.
- [x] 3. `set_timer` tool. *Done when:* an alert fires after N minutes.
- [x] 4. `set_reminder` at a clock time, persisted in SQLite. *Done when:* it survives a restart.
- [x] 5. Alerts are spoken and printed. *Done when:* both happen when a reminder fires.

## Phase 8: Email and calendar (Google)
1. Create a Google Cloud project, enable the Gmail and Calendar APIs, and document it. *Done when:* `credentials.json` is available locally.
2. Add the OAuth login flow with local token storage and minimal scopes. *Done when:* the first run opens a browser and later runs reuse the token.
3. `list_events`: view today's and upcoming events. *Done when:* "what's on today?" answers correctly.
4. `create_event` and `edit_event` (risky): require confirmation. *Done when:* an event is created or changed only after "yes".
5. `read_emails`: list recent or unread messages. *Done when:* the latest emails are listed.
6. `summarize_email`: summarize a message or thread with the LLM. *Done when:* a chosen email gets a short summary.
7. `draft_email`: save a draft in Gmail. *Done when:* the draft appears in Gmail.
8. `send_email` (risky): send after showing the recipient, subject and body for confirmation. *Done when:* nothing is sent without "yes".
9. Proactive alerts for upcoming events (poll via scheduler). *Done when:* an alert fires N minutes before an event.
10. Proactive alerts for new important email (e.g. Gmail "important" label, configurable). *Done when:* a new important email triggers a spoken/text notice.
11. Add a config option to turn each proactive alert on or off. *Done when:* disabling stops the polling.

## Phase 9: Floating character
1. Add an event bus emitting idle/listening/thinking/speaking. *Done when:* events log in the CLI.
2. Show a transparent, frameless, always-on-top emoji window. *Done when:* the emoji floats over other apps.
3. Change the emoji per state. *Done when:* it changes as Jarvis moves between states.
4. Let the user drag it. *Done when:* the position is remembered.
5. Add idle movement/animation around the screen (optional toggle). *Done when:* it moves without blocking clicks.
6. Add a system tray icon with Quit and Mute. *Done when:* both work.
7. Add a Playful/Formal setting that changes the character and the LLM tone. *Done when:* switching it changes both.
8. Click the character to open a small text input. *Done when:* typed requests work from the overlay.

## Phase 10: Help when stuck
1. Add a "help" system prompt mode that explains step by step. *Done when:* "I'm stuck on X" gives clear steps.
2. Let help mode use tools and web search automatically. *Done when:* an unknown question triggers a search.
3. Add a hotkey or character menu entry for "I need help". *Done when:* it starts a help conversation.

## Phase 11: Advanced
1. Wake-word activation ("Hey Jarvis"). *Done when:* it triggers hands-free, with a toggle to disable.
2. Screenshot capture tool. *Done when:* a screenshot is saved on request.
3. Vision model for screenshots in help mode. *Done when:* Jarvis describes what is on screen and suggests next steps.
4. Full animated character replacing the emoji. *Done when:* animations map to each state.
5. Packaging and start-on-login. *Done when:* a fresh Windows user can install and launch Jarvis at login.

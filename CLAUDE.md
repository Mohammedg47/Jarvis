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

Package `jarvis/` with submodules `core` (config, logging, main loop), `llm`, `tools`, `voice`, `memory`, `ui`. `core`, `llm` and `ui` have code so far; `tools`, `voice` and `memory` are empty placeholders for later roadmap phases.

- **Config** (`jarvis/core/config.py`): `get_settings()` returns a pydantic `Settings` loaded from environment variables and a local `.env` (copy `.env.example`). Variables use the `JARVIS_` prefix, except `ELEVENLABS_API_KEY`.
- **Logging** (`jarvis/core/logging.py`): `setup_logging(settings)` logs to the console and a rotating file.
- **LLM** (`jarvis/llm/`): `OllamaClient.chat(messages)` streams reply chunks from the local model; `build_system_prompt(personality)` assembles the prompt from `jarvis/llm/prompts/*.md` (edit those files to change behavior). Errors surface as `LLMError`.
- **Conversation** (`jarvis/core/conversation.py`): holds message history and streams replies; independent of the UI so voice and text can share it.
- **CLI** (`jarvis/ui/cli.py`): terminal chat loop with `/clear`, `/help`, `/exit`. Uses prompt_toolkit in a real console and plain `input()` when stdin is piped.
- **Ollama setup**: install Ollama (`winget install Ollama.Ollama`) and run `ollama pull qwen2.5:3b`. This model was benchmarked on the dev laptop (GTX 1050, 4 GB VRAM) to run fully on the GPU; 7-8B models do not fit. Change it with `JARVIS_OLLAMA_MODEL`.
- **Data directory**: `%APPDATA%\Jarvis` by default (override with `JARVIS_DATA_DIR`). Logs and, later, the memory database live here, outside the repo.

Planned design rules (see `specs/techstack.md`): tools are registered in a registry with a `safe`/`risky` level; every tool call passes one permission gate, and risky actions need user confirmation.

## Notes

- Development is on Windows (PowerShell primary, Git Bash available).
- Default branch is `main`.
- Never commit `.env`, `credentials.json` or `token.json`.

# Mission

## Purpose
Jarvis is an AI assistant that lives on the user's Windows laptop. The user talks to it by voice or text, and it acts as an almost admin-like helper: it opens and closes applications, manages files, controls the system, searches the web, sets reminders, and helps the user when they are stuck.

## Target user
A single laptop owner who wants a hands-free, always-available, personable assistant without sending their whole machine's activity to the cloud.

## Core capabilities
1. **Conversation** by voice (ElevenLabs speech-to-text and text-to-speech) and by text. Both interfaces are first-class and share one conversation.
2. **Admin actions**: open/close apps, file operations (search, open, create, move, delete), system control (volume, lock, etc.), reminders and timers.
3. **Web search** for answers and lookups.
4. **Help when stuck**: the user asks, and Jarvis uses its tools and web search to answer. Later, it can use a screenshot to see what the user is looking at.
5. **Email and calendar (Google)**: read and summarize Gmail, draft and send emails, view Google Calendar, and create/edit events. Sending email and creating, editing or deleting events require confirmation. Jarvis proactively alerts the user about upcoming events and new important email.
6. **Memory**: remembers conversations and preferences across sessions, stored locally.
7. **Presence**: a small floating character (emoji face first, full animated character later) shows that Jarvis is online and working (idle, listening, thinking, speaking). Personality is user-selectable: Playful or Formal.

## Principles
- **Local-first and private**: the LLM runs locally through Ollama. Memory stays on disk. Only speech audio/text goes to ElevenLabs, and web searches go out only when requested.
- **Safe by default**: risky or irreversible actions (closing apps, deleting files, shutdown) require explicit user confirmation.
- **Voice and text parity**: anything possible by voice is possible by text.
- **Modular tools**: each ability is a small, self-contained, testable tool registered with the assistant.
- **Simple steps**: the project is built in small phases that each leave a working system.
- **Configurable**: model name, voice, hotkey and personality are settings, not hard-coded.

## Platform and constraints
- Windows only.
- Python.
- Must run on an ordinary laptop, so the default model is small (3-8B parameters).
- Secrets (ElevenLabs API key) live in `.env` and are never committed.

## Out of scope (for now)
- macOS/Linux support.
- Mobile or multi-device sync.
- Multi-user accounts.
- Non-Google email/calendar providers (Outlook, IMAP/CalDAV).
- Autonomous actions without the user asking.

## Success criteria
- User says or types "open Notepad" and it opens; "close it" asks for confirmation, then closes.
- Voice round trip (hotkey, speak, answer spoken back) feels conversational.
- Jarvis recalls a preference stated in an earlier session.
- No destructive action ever runs without confirmation.
- The floating character always reflects Jarvis's current state.

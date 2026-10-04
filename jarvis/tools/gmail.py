"""Gmail tools. Drafting is safe; sending is risky and shows recipient, subject and body."""

import base64
import re
from email.message import EmailMessage
from html import unescape

from jarvis.google.service import google_tool, service
from jarvis.tools.registry import RISKY, tool

MAX_EMAILS = 10
MAX_BODY_CHARS = 4000
_ADDRESS = re.compile(r"^[^@\s,;<>]+@[^@\s,;<>]+\.[^@\s,;<>]+$")
# Zero-width and similar padding characters marketing email hides in previews.
_INVISIBLE = dict.fromkeys([*range(0x200B, 0x2010), 0x34F, 0x2060, 0xFEFF])


def header(message: dict, name: str) -> str:
    for h in message.get("payload", {}).get("headers", []):
        if h["name"].lower() == name.lower():
            return h["value"]
    return ""


def extract_body(payload: dict) -> str:
    """Plain-text body of a Gmail message payload; falls back to tag-stripped HTML."""

    def find(part: dict, mime: str) -> str | None:
        data = part.get("body", {}).get("data")
        if part.get("mimeType") == mime and data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for child in part.get("parts", []):
            found = find(child, mime)
            if found:
                return found
        return None

    text = find(payload, "text/plain")
    if text is None:
        html = find(payload, "text/html") or ""
        text = unescape(re.sub(r"<(style|script).*?</\1>|<[^>]+>", " ", html, flags=re.DOTALL))
    return re.sub(r"\s+", " ", text).strip()


def _fetch_summary(gmail, message_id: str) -> dict:
    return (
        gmail.users()
        .messages()
        .get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Subject", "Date"],
        )
        .execute()
    )


def clean_snippet(text: str) -> str:
    """Decode HTML entities and drop the invisible padding characters marketing mail uses."""
    text = unescape(text).translate(_INVISIBLE)
    return re.sub(r"\s+", " ", text).strip()


def format_message(message: dict) -> str:
    unread = "UNREAD " if "UNREAD" in message.get("labelIds", []) else ""
    return (
        f"[{message['id']}] {unread}From: {header(message, 'From')} | "
        f"Subject: {header(message, 'Subject') or '(no subject)'} | "
        f"Date: {header(message, 'Date')}\n    {clean_snippet(message.get('snippet', ''))[:150]}"
    )


@tool()
@google_tool
def read_emails(unread_only: bool = True, count: int = 5, query: str = "") -> str:
    """List recent emails from the Gmail inbox (sender, subject, date, short preview). Use it for "any new email?".

    Args:
        unread_only: Only unread messages.
        count: How many to list (at most 10).
        query: Optional Gmail search, e.g. "from:alice" or "subject:invoice".
    """
    gmail = service("gmail", "v1")
    q = " ".join(p for p in ("is:unread" if unread_only else "", query) if p)
    listing = (
        gmail.users()
        .messages()
        .list(userId="me", labelIds=["INBOX"], q=q, maxResults=max(1, min(count, MAX_EMAILS)))
        .execute()
    )
    ids = [m["id"] for m in listing.get("messages", [])]
    if not ids:
        return "No matching emails."
    return "\n".join(format_message(_fetch_summary(gmail, i)) for i in ids)


@tool()
@google_tool
def summarize_email(message_id: str) -> str:
    """Fetch one email's text so you can summarize it in two or three short sentences. Get the message_id from read_emails.

    Args:
        message_id: The id shown in square brackets by read_emails.
    """
    gmail = service("gmail", "v1")
    message = gmail.users().messages().get(userId="me", id=message_id, format="full").execute()
    body = extract_body(message.get("payload", {})) or "(no text content)"
    truncated = " [truncated]" if len(body) > MAX_BODY_CHARS else ""
    return (
        f"From: {header(message, 'From')}\nSubject: {header(message, 'Subject')}\n"
        f"Date: {header(message, 'Date')}\n\n{body[:MAX_BODY_CHARS]}{truncated}"
    )


def _build_raw(to: str, subject: str, body: str) -> str:
    msg = EmailMessage()
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    return base64.urlsafe_b64encode(msg.as_bytes()).decode()


def _bad_address(to: str) -> str | None:
    if not _ADDRESS.match(to.strip()):
        return f"Error: '{to}' is not a single valid email address."
    return None


@tool(risk=RISKY)
@google_tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email now. Use this whenever the user says send, email or message someone. Call it straight away: the app shows the user the recipient, subject and body and asks them to confirm. Write the final text; never use placeholders.

    Args:
        to: Recipient email address.
        subject: Subject line.
        body: Plain-text message body.
    """
    if problem := _bad_address(to):
        return problem
    service("gmail", "v1").users().messages().send(
        userId="me", body={"raw": _build_raw(to.strip(), subject, body)}
    ).execute()
    return f"Email sent to {to}: {subject}"


@tool()
@google_tool
def draft_email(to: str, subject: str, body: str) -> str:
    """Save an email as an unsent draft. Use ONLY when the user explicitly says draft or save for later. If the user says send, email or message someone, use send_email instead.

    Args:
        to: Recipient email address.
        subject: Subject line.
        body: Plain-text message body.
    """
    if problem := _bad_address(to):
        return problem
    draft = (
        service("gmail", "v1")
        .users()
        .drafts()
        .create(userId="me", body={"message": {"raw": _build_raw(to.strip(), subject, body)}})
        .execute()
    )
    return f"Draft saved in Gmail (id {draft['id']}) to {to}: {subject}"

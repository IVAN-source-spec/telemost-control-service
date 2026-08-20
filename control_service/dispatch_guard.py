from __future__ import annotations

import asyncio
from urllib.parse import urlsplit, urlunsplit


meeting_dispatch_lock = asyncio.Lock()


def normalize_meeting_url(value: str | None) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    path = parsed.path.rstrip("/")
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def active_assignment(statuses: list[dict], meeting_url: str) -> dict | None:
    expected = normalize_meeting_url(meeting_url)
    if not expected:
        return None
    for status in statuses:
        for bot in status.get("bots") or []:
            if bot.get("status") != "busy":
                continue
            if normalize_meeting_url(bot.get("meeting_url")) == expected:
                return {
                    "node_id": status.get("node_id"),
                    "node_name": status.get("node_name"),
                    "bot_id": bot.get("bot_id"),
                    "session_id": bot.get("session_id"),
                    "meeting_url": bot.get("meeting_url"),
                }
    return None

"""Saves chats to a local JSON file so you can come back to earlier ones.

A chat is one conversation: its messages plus the agent's state (what it has
learned about your taste, liked/disliked songs), enough to pick up where you
left off. Recommendations are not stored; they are recomputed on resume.
"""

import json
import os
from datetime import datetime
from typing import Dict, List

CHATS_PATH = "data/chats.json"  # tests point this somewhere temporary
MAX_CHATS = 50


def load_all() -> List[Dict]:
    """All saved chats, most recently updated first. Unreadable file -> empty."""
    try:
        with open(CHATS_PATH, encoding="utf-8") as f:
            chats = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(chats, list):
        return []
    return sorted(chats, key=lambda c: c.get("updated", ""), reverse=True)


def _write(chats: List[Dict]) -> None:
    chats = sorted(chats, key=lambda c: c.get("updated", ""), reverse=True)[:MAX_CHATS]
    tmp = CHATS_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(chats, f, ensure_ascii=False)
    os.replace(tmp, CHATS_PATH)  # atomic, so a crash can't leave half a file


def make_title(messages: List[Dict]) -> str:
    for msg in messages:
        if msg["role"] == "user":
            text = " ".join(msg["content"].split())
            return text if len(text) <= 42 else text[:41] + "…"
    return "New chat"


def save_chat(chat_id: str, messages: List[Dict], stage: str, agent_state: Dict) -> None:
    chats = [c for c in load_all() if c["id"] != chat_id]
    chats.append({
        "id": chat_id,
        "title": make_title(messages),
        "updated": datetime.now().isoformat(timespec="seconds"),
        "stage": stage,
        "messages": messages,
        "agent": agent_state,
    })
    _write(chats)


def delete_chat(chat_id: str) -> None:
    _write([c for c in load_all() if c["id"] != chat_id])


def get_chat(chat_id: str) -> Dict | None:
    return next((c for c in load_all() if c["id"] == chat_id), None)


def when(iso: str) -> str:
    """Short human-readable time like 'Nov 15, 6:12 PM'."""
    try:
        return datetime.fromisoformat(iso).strftime("%b %d, %I:%M %p").replace(" 0", " ")
    except ValueError:
        return ""

from __future__ import annotations

from typing import Any


def extract_text(text_data: Any) -> str:
    if isinstance(text_data, str):
        return text_data
    if isinstance(text_data, list):
        out: list[str] = []
        for part in text_data:
            if isinstance(part, str):
                out.append(part)
            elif isinstance(part, dict):
                out.append(str(part.get("text") or ""))
        return "".join(out)
    return ""


def get_participants(chat_json: dict) -> list[dict[str, str | int]]:
    users_map: dict[str, str] = {}
    counts: dict[str, int] = {}
    for message in chat_json.get("messages", []) or []:
        if (
            isinstance(message, dict)
            and message.get("from")
            and message.get("from_id")
            and message.get("type") == "message"
        ):
            uid = str(message["from_id"])
            users_map[uid] = str(message["from"])
            text = extract_text(message.get("text"))
            if text and text.strip():
                counts[uid] = counts.get(uid, 0) + 1

    participants = [
        {"id": uid, "name": name, "messageCount": counts.get(uid, 0)}
        for uid, name in users_map.items()
    ]
    participants.sort(key=lambda item: (-int(item["messageCount"]), item["name"].lower()))
    return participants


def get_user_messages(chat_json: dict, user_id: str) -> list[str]:
    msgs: list[str] = []
    for message in chat_json.get("messages", []) or []:
        if not isinstance(message, dict):
            continue
        if str(message.get("from_id")) != str(user_id):
            continue
        if message.get("type") != "message":
            continue
        text = extract_text(message.get("text"))
        if text and text.strip():
            msgs.append(text)
    return msgs


def get_username(chat_json: dict, user_id: str) -> str | None:
    for message in chat_json.get("messages", []) or []:
        if not isinstance(message, dict):
            continue
        if str(message.get("from_id")) != str(user_id):
            continue
        name = message.get("from")
        if name:
            return str(name)
    return None


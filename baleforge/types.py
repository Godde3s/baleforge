"""Typed objects mirroring the Bale Bot API (Telegram-compatible)."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class User:
    id: int
    first_name: str
    last_name: str = ""
    username: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "User":
        return cls(
            id=d.get("id", 0),
            first_name=d.get("first_name", ""),
            last_name=d.get("last_name", ""),
            username=d.get("username", ""),
        )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass(frozen=True)
class Chat:
    id: int
    type: str = "private"
    title: str = ""

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Chat":
        return cls(id=d.get("id", 0), type=d.get("type", "private"),
                   title=d.get("title", ""))


@dataclass(frozen=True)
class InlineButton:
    text: str
    callback_data: str = ""
    url: str = ""

    def to_dict(self) -> dict[str, str]:
        d: dict[str, str] = {"text": self.text}
        if self.callback_data:
            d["callback_data"] = self.callback_data
        if self.url:
            d["url"] = self.url
        return d


@dataclass(frozen=True)
class InlineKeyboard:
    """Inline keyboard — rows of buttons, Telegram/Bale style."""

    rows: list[list[InlineButton]] = field(default_factory=list)

    @classmethod
    def of(cls, *buttons: InlineButton, per_row: int = 2) -> "InlineKeyboard":
        rows = [list(buttons[i : i + per_row]) for i in range(0, len(buttons), per_row)]
        return cls(rows=rows)

    def to_dict(self) -> dict[str, Any]:
        return {"inline_keyboard": [[b.to_dict() for b in row] for row in self.rows]}


@dataclass(frozen=True)
class Message:
    message_id: int
    chat: Chat
    from_user: User | None
    text: str = ""
    date: int = 0
    caption: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Message":
        return cls(
            message_id=d.get("message_id", 0),
            chat=Chat.from_dict(d.get("chat", {})),
            from_user=User.from_dict(d["from"]) if "from" in d else None,
            text=d.get("text", ""),
            date=d.get("date", 0),
            caption=d.get("caption", ""),
            raw=d,
        )

    @property
    def chat_id(self) -> int:
        return self.chat.id


@dataclass(frozen=True)
class CallbackQuery:
    id: str
    from_user: User | None
    data: str = ""
    message: Message | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CallbackQuery":
        return cls(
            id=d.get("id", ""),
            from_user=User.from_dict(d["from"]) if "from" in d else None,
            data=d.get("data", ""),
            message=Message.from_dict(d["message"]) if "message" in d else None,
        )


@dataclass(frozen=True)
class Update:
    update_id: int
    message: Message | None = None
    callback_query: CallbackQuery | None = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Update":
        return cls(
            update_id=d.get("update_id", 0),
            message=Message.from_dict(d["message"]) if "message" in d else None,
            callback_query=CallbackQuery.from_dict(d["callback_query"])
            if "callback_query" in d
            else None,
        )

    @property
    def effective_chat_id(self) -> int | None:
        if self.message:
            return self.message.chat_id
        if self.callback_query and self.callback_query.message:
            return self.callback_query.message.chat_id
        return None

    @property
    def effective_user(self) -> User | None:
        if self.message:
            return self.message.from_user
        if self.callback_query:
            return self.callback_query.from_user
        return None

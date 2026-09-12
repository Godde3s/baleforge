"""Async HTTP client for the Bale Bot API.

Bale's bot API is Telegram-compatible and served from
``https://tapi.bale.ai/bot<TOKEN>/<method>``. This module is the only
place that knows about HTTP — everything above works against typed
objects and never sees a status code.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

log = logging.getLogger("baleforge")

BASE_URL = "https://tapi.bale.ai/bot{token}/{method}"


class BaleAPIError(RuntimeError):
    """Raised when the Bale API returns an error response."""

    def __init__(self, method: str, description: str, code: int | None = None):
        super().__init__(f"{method} failed ({code}): {description}")
        self.method = method
        self.description = description
        self.code = code


class BaleClient:
    """Thin, retrying, fully async Bale Bot API client."""

    def __init__(
        self,
        token: str,
        base_url: str = BASE_URL,
        timeout: float = 30.0,
        max_retries: int = 3,
    ) -> None:
        self.token = token
        self._base = base_url
        self._max_retries = max_retries
        self._client = httpx.AsyncClient(timeout=timeout)

    async def close(self) -> None:
        await self._client.aclose()

    async def call(self, method: str, **payload: Any) -> dict[str, Any]:
        """Invoke an API method with exponential backoff on transient errors."""
        url = self._base.format(token=self.token, method=method)
        payload = {k: v for k, v in payload.items() if v is not None}
        delay = 1.0

        last_error: Exception | None = None
        for attempt in range(1, self._max_retries + 1):
            try:
                resp = await self._client.post(url, json=payload)
                data = resp.json()
                if data.get("ok"):
                    return data["result"]
                raise BaleAPIError(method, str(data.get("description", "unknown")),
                                   resp.status_code)
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_error = exc
                log.warning("%s transient error (attempt %d): %s",
                            method, attempt, exc)
                await asyncio.sleep(delay)
                delay *= 2
        raise BaleAPIError(method, f"transport failed after retries: {last_error}")

    # ---- convenience wrappers -------------------------------------------

    async def get_me(self) -> dict[str, Any]:
        return await self.call("getMe")

    async def get_updates(self, offset: int | None = None, timeout: int = 25) -> list[dict]:
        return await self.call("getUpdates", offset=offset, timeout=timeout,
                               allowed_updates=["message", "callback_query"])

    async def send_message(
        self,
        chat_id: int | str,
        text: str,
        reply_markup: dict | None = None,
        reply_to_message_id: int | None = None,
        parse_mode: str | None = None,
    ) -> dict[str, Any]:
        return await self.call(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
            parse_mode=parse_mode,
        )

    async def send_chat_action(self, chat_id: int | str, action: str = "typing") -> dict:
        return await self.call("sendChatAction", chat_id=chat_id, action=action)

    async def answer_callback_query(self, callback_query_id: str, text: str = "") -> dict:
        return await self.call("answerCallbackQuery",
                               callback_query_id=callback_query_id, text=text)

    async def edit_message_text(self, chat_id: int | str, message_id: int,
                                text: str, reply_markup: dict | None = None) -> dict:
        return await self.call("editMessageText", chat_id=chat_id,
                               message_id=message_id, text=text,
                               reply_markup=reply_markup)

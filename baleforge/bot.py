"""BaleForge — the Bot class and the long-polling engine."""

from __future__ import annotations

import asyncio
import logging
import signal
from typing import Any

from .agent import AgentBridge
from .api import BaleClient
from .dispatcher import Dispatcher, FSM
from .types import Update, InlineKeyboard

log = logging.getLogger("baleforge")


class Bot:
    """One Bot = one token. Compose routers, middleware, FSM and an agent."""

    def __init__(self, token: str, name: str = "bot") -> None:
        self.client = BaleClient(token)
        self.name = name
        self.me: dict[str, Any] = {}
        self.dispatcher = Dispatcher(self.client, FSM())
        self.agent: AgentBridge | None = None

    # ---- composition ------------------------------------------------------

    def include(self, router) -> "Bot":
        self.dispatcher.include(router)
        return self

    def use(self, middleware) -> "Bot":
        self.dispatcher.use(middleware)
        return self

    def attach_agent(self, agent: AgentBridge) -> "Bot":
        self.agent = agent
        return self

    # ---- convenience sends -------------------------------------------------

    async def send(self, chat_id: int, text: str,
                   keyboard: InlineKeyboard | None = None, **kw) -> dict:
        return await self.client.send_message(
            chat_id, text,
            reply_markup=keyboard.to_dict() if keyboard else None, **kw
        )

    async def typing(self, chat_id: int) -> None:
        await self.client.send_chat_action(chat_id, "typing")

    # ---- lifecycle ----------------------------------------------------------

    async def poll_forever(self, drop_pending: bool = True) -> None:
        """Long-polling loop: the heart of the framework."""
        self.me = await self.client.get_me()
        log.info("polling as @%s (%s)", self.me.get("username", self.name),
                 self.me.get("first_name", ""))

        offset: int | None = None
        backoff = 2.0
        while True:
            try:
                updates = await self.client.get_updates(offset=offset, timeout=25)
                backoff = 2.0
                for raw in updates:
                    update = Update.from_dict(raw)
                    offset = update.update_id + 1
                    if drop_pending and update.message and \
                       update.message.date and _is_stale(update.message.date):
                        log.debug("dropping stale update %s", update.update_id)
                        continue
                    try:
                        handled = await self.dispatcher.feed(update)
                        if not handled:
                            log.debug("no handler for update %s", update.update_id)
                    except Exception:
                        log.exception("handler crashed on update %s", update.update_id)
                        if update.effective_chat_id:
                            await self.client.send_message(
                                update.effective_chat_id,
                                "⚠️ خطای داخلی رخ داد. لطفاً دوباره تلاش کنید."
                            )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("poll loop error: %s — retrying in %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)

    async def run(self) -> None:
        """Blocking run() with graceful SIGINT/SIGTERM shutdown."""
        loop = asyncio.get_running_loop()
        stop = loop.create_future()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, stop.set_result, None)
            except NotImplementedError:      # Windows
                pass

        poller = asyncio.ensure_future(self.poll_forever())
        log.info("%s started — Ctrl+C to stop", self.name)
        try:
            await stop
        finally:
            poller.cancel()
            try:
                await poller
            except asyncio.CancelledError:
                pass
            await self.client.close()
            log.info("%s stopped cleanly", self.name)


def _is_stale(message_date: int, max_age: int = 300) -> bool:
    import time

    return (time.time() - message_date) > max_age

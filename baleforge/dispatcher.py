"""Router, filters and middleware — the dispatching core of BaleForge.

Handlers are registered with filters; the first handler whose filters all
accept an update wins. Middleware wraps the whole dispatch pipeline.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .types import Update

log = logging.getLogger("baleforge")

Handler = Callable[[Any], Awaitable[None]]          # receives Context
Middleware = Callable[[Any, Handler], Awaitable[None]]


# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

def command(*names: str):
    """Match /commands, optionally with @bot suffix, case-insensitive."""
    wanted = {n.lower().lstrip("/") for n in names}

    async def _filter(ctx: Any) -> bool:
        msg = ctx.update.message
        if not msg or not msg.text or not msg.text.startswith("/"):
            return False
        head = msg.text.split()[0].split("@")[0].lower()
        return head[1:] in wanted

    return _filter


def text(match: str | None = None, contains: str | None = None,
         regex: str | None = None):
    """Match message text exactly / by substring / by pattern."""

    async def _filter(ctx: Any) -> bool:
        msg = ctx.update.message
        if not msg or not msg.text:
            return False
        if match is not None and msg.text.strip() != match:
            return False
        if contains is not None and contains not in msg.text:
            return False
        if regex is not None and not re.search(regex, msg.text):
            return False
        return match is not None or contains is not None or regex is not None

    return _filter


def chat_type(*types: str):
    """Match chat type: private, group, channel..."""

    async def _filter(ctx: Any) -> bool:
        msg = ctx.update.message
        return bool(msg and msg.chat.type in types)

    return _filter


def from_user(*user_ids: int):
    """Restrict a handler to specific user ids (access control)."""
    allowed = set(user_ids)

    async def _filter(ctx: Any) -> bool:
        user = ctx.update.effective_user
        return bool(user and user.id in allowed)

    return _filter


def state(name: str | None):
    """Match the user's FSM state; ``None`` matches "no state"."""
    async def _filter(ctx: Any) -> bool:
        current = await ctx.fsm.get_state(ctx.update)
        return current == name

    return _filter


def callback(pattern: str = ""):
    """Match callback queries, optionally whose data matches a regex."""

    async def _filter(ctx: Any) -> bool:
        cb = ctx.update.callback_query
        if cb is None:
            return False
        return bool(re.fullmatch(pattern, cb.data)) if pattern else True

    return _filter


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

@dataclass
class Context:
    """Everything a handler needs: the update, the bot API and helpers."""

    update: Update
    bot: Any                                # BaleClient (typed loosely to avoid cycle)
    fsm: "FSM"
    data: dict[str, Any] = field(default_factory=dict)

    async def reply(self, text: str, **kwargs) -> dict:
        chat_id = self.update.effective_chat_id
        return await self.bot.send_message(chat_id, text, **kwargs)

    async def answer_callback(self, text: str = "") -> dict:
        cb = self.update.callback_query
        return await self.bot.answer_callback_query(cb.id, text)


# ---------------------------------------------------------------------------
# Router + Dispatcher
# ---------------------------------------------------------------------------

@dataclass
class _Route:
    filters: list
    handler: Handler
    name: str


class Router:
    def __init__(self) -> None:
        self._routes: list[_Route] = []

    def message(self, *filters, name: str = "") -> Callable[[Handler], Handler]:
        return self._register(list(filters), name)

    def callback_query(self, *filters, name: str = "") -> Callable[[Handler], Handler]:
        return self._register([callback(), *filters], name)

    def _register(self, filters: list, name: str):
        def deco(fn: Handler) -> Handler:
            self._routes.append(_Route(filters, fn, name or fn.__name__))
            return fn
        return deco

    async def dispatch(self, ctx: Context) -> bool:
        for route in self._routes:
            try:
                checks = [await f(ctx) for f in route.filters]
            except Exception:
                log.exception("filter error in route %s", route.name)
                continue
            if all(checks):
                await route.handler(ctx)
                return True
        return False


class Dispatcher:
    """Feeds updates through middleware into routers."""

    def __init__(self, bot: Any, fsm: "FSM") -> None:
        self.bot = bot
        self.fsm = fsm
        self.routers: list[Router] = []
        self.middlewares: list[Middleware] = []

    def include(self, router: Router) -> Router:
        self.routers.append(router)
        return router

    def use(self, mw: Middleware) -> None:
        self.middlewares.append(mw)

    async def feed(self, update: Update) -> bool:
        ctx = Context(update=update, bot=self.bot, fsm=self.fsm)

        async def _base(ctx: Context) -> bool:
            for router in self.routers:
                if await router.dispatch(ctx):
                    return True
            return False

        chain = _base
        for mw in reversed(self.middlewares):
            chain = _bind(mw, chain)
        return bool(await chain(ctx))


def _bind(mw: Middleware, nxt) -> Handler:
    async def _wrapped(ctx: Context):
        return await mw(ctx, nxt)
    return _wrapped


# ---------------------------------------------------------------------------
# FSM (finite state machine) with pluggable in-memory storage
# ---------------------------------------------------------------------------

class MemoryStorage:
    def __init__(self) -> None:
        self._data: dict[str, dict] = {}

    async def get(self, key: str) -> dict:
        return dict(self._data.get(key, {}))

    async def set(self, key: str, value: dict) -> None:
        self._data[key] = dict(value)

    async def clear(self, key: str) -> None:
        self._data.pop(key, None)


class FSM:
    """Per-user finite state machine — registration wizards, forms, quizzes."""

    def __init__(self, storage: MemoryStorage | None = None) -> None:
        self.storage = storage or MemoryStorage()

    @staticmethod
    def _key(update: Update) -> str:
        user = update.effective_user
        return f"u:{user.id if user else 0}"

    async def get_state(self, update: Update) -> str | None:
        data = await self.storage.get(FSM._key(update))
        return data.get("state")

    async def set_state(self, update: Update, state: str | None) -> None:
        key = FSM._key(update)
        data = await self.storage.get(key)
        if state is None:
            data.pop("state", None)
        else:
            data["state"] = state
        await self.storage.set(key, data)

    async def get_data(self, update: Update) -> dict:
        return await self.storage.get(FSM._key(update))

    async def update_data(self, update: Update, **kv) -> dict:
        key = FSM._key(update)
        data = await self.storage.get(key)
        data.update(kv)
        await self.storage.set(key, data)
        return data

    async def reset(self, update: Update) -> None:
        await self.storage.clear(FSM._key(update))

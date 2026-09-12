"""Dispatcher, filter and FSM tests — no network required."""

import asyncio

import pytest

from baleforge import Bot, Router, command, state, text
from baleforge.dispatcher import FSM, Context, Dispatcher, MemoryStorage
from baleforge.types import Chat, Message, Update, User


def make_update(text_str: str, user_id: int = 42, update_id: int = 1) -> Update:
    msg = Message(
        message_id=update_id,
        chat=Chat(id=100, type="private"),
        from_user=User(id=user_id, first_name="Test"),
        text=text_str,
        date=1_700_000_000,
    )
    return Update(update_id=update_id, message=msg)


class FakeBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, **kw):
        self.sent.append((chat_id, text, kw))
        return {"ok": True}

    async def typing(self, chat_id):
        pass


@pytest.fixture
def dispatcher():
    bot = FakeBot()
    dp = Dispatcher(bot, FSM())
    return dp, bot


async def test_command_filter_routes_to_right_handler(dispatcher):
    dp, bot = dispatcher
    router = Router()

    hits = []

    @router.message(command("start"))
    async def on_start(ctx):
        hits.append("start")
        await ctx.reply("welcome")

    @router.message()
    async def fallback(ctx):
        hits.append("fallback")

    dp.include(router)
    assert await dp.feed(make_update("/start")) is True
    assert hits == ["start"]
    assert bot.sent[0][1] == "welcome"

    assert await dp.feed(make_update("just words")) is True
    assert hits == ["start", "fallback"]


async def test_first_matching_handler_wins(dispatcher):
    dp, bot = dispatcher
    router = Router()
    hits = []

    @router.message(text(contains="salam"))
    async def first(ctx):
        hits.append(1)

    @router.message(text(contains="salam"))
    async def second(ctx):
        hits.append(2)

    dp.include(router)
    await dp.feed(make_update("salam dost man"))
    assert hits == [1]


async def test_fsm_state_transitions(dispatcher):
    dp, bot = dispatcher
    router = Router()
    fsm = FSM(MemoryStorage())
    answers = []

    @router.message(command("form"))
    async def begin(ctx):
        await ctx.fsm.set_state(ctx.update, "waiting:age")
        await ctx.reply("senet chande?")

    @router.message(state("waiting:age"))
    async def collect(ctx):
        answers.append(ctx.update.message.text)
        await ctx.fsm.reset(ctx.update)
        await ctx.reply("sabt shod")

    @router.message()
    async def other(ctx):
        await ctx.reply("?")

    dp.include(router)
    dp.fsm = fsm
    ctx_update = make_update("/form")
    await dp.feed(ctx_update)
    assert await fsm.get_state(ctx_update) == "waiting:age"

    await dp.feed(make_update("27", update_id=2))
    assert answers == ["27"]
    assert await fsm.get_state(make_update("x", update_id=3)) is None


async def test_middleware_wraps_pipeline(dispatcher):
    dp, bot = dispatcher
    router = Router()
    order = []

    async def mw(ctx, nxt):
        order.append("before")
        result = await nxt(ctx)
        order.append("after")
        return result

    dp.use(mw)

    @router.message()
    async def anything(ctx):
        order.append("handler")
        return True

    dp.include(router)
    await dp.feed(make_update("hi"))
    assert order == ["before", "handler", "after"]


async def test_unhandled_update_returns_false(dispatcher):
    dp, _ = dispatcher
    assert await dp.feed(make_update("nobody listens")) is False

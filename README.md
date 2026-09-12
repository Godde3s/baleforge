# BaleForge

<p align="center">
  <strong>فریم‌ورک مدرن برای ساخت ربات‌های بله — سریع، تایپ‌دار و مبتنی بر ایجنت</strong><br>
  A modern async framework for building Bale messenger bots.<br>
  Telegram-compatible API · declarative filters · FSM · middleware · AI agent bridge
</p>

<p align="center">
  <a href="https://github.com/Godde3s/baleforge/actions">CI</a> ·
  <a href="#quick-start">Quick Start</a> ·
  <a href="#the-ai-agent-bridge">AI Agent</a> ·
  <a href="#فارسی">مستندات فارسی</a>
</p>

---

## Why BaleForge

Bale is the messaging platform millions of Iranians actually use — yet bot
development on it means hand-rolling `getUpdates` loops and JSON dicts.
**BaleForge gives Bale the developer experience modern frameworks offer:**

- **Fully async** — one process, thousands of chats, `httpx` under the hood
- **Typed objects** — `Update`, `Message`, `CallbackQuery`, `InlineKeyboard`;
  no more `data["message"]["chat"]["id"]` chains
- **Declarative filters** — `command("start")`, `text(contains=...)`,
  `from_user(...)`, `chat_type(...)`, `state(...)`, `callback(...)`
- **FSM included** — multi-step wizards and forms with pluggable storage
- **Middleware pipeline** — logging, rate limiting, auth, in the right order
- **AI agent bridge** — give your bot a brain with function-calling, in ~10 lines
- **Production hardening** — retry with exponential backoff, stale-update
  drop, per-update error isolation, graceful SIGINT shutdown

## Quick Start

```bash
pip install baleforge
export BALE_TOKEN="123:abc"   # from @BotFather on Bale
python examples/echo_bot.py
```

Your first bot:

```python
import asyncio, os
from baleforge import Bot, Router, command

router = Router()

@router.message(command("start"))
async def start(ctx):
    await ctx.reply("سلام! من با BaleForge ساخته شدم 🚀")

async def main():
    await Bot(os.environ["BALE_TOKEN"]).include(router).run()

asyncio.run(main())
```

### Inline keyboards and callbacks

```python
from baleforge import InlineButton, InlineKeyboard

@router.message(command("menu"))
async def menu(ctx):
    kb = InlineKeyboard.of(
        InlineButton("وضعیت", callback_data="status"),
        InlineButton("وب‌سایت", url="https://example.com"),
    )
    await ctx.reply("یک گزینه انتخاب کن:", reply_markup=kb.to_dict())

@router.callback_query()
async def on_button(ctx):
    await ctx.answer_callback("انجام شد ✅")
```

### Forms with FSM

```python
from baleforge import state

@router.message(command("register"))
async def begin(ctx):
    await ctx.fsm.set_state(ctx.update, "age")
    await ctx.reply("سنّت چنده؟")

@router.message(state("age"))
async def collect(ctx):
    await ctx.fsm.update_data(ctx.update, age=ctx.update.message.text)
    await ctx.fsm.set_state(ctx.update, None)
    await ctx.reply("ثبت شد ✅")
```

## The AI Agent Bridge

Point it at **any OpenAI-compatible endpoint** — OpenAI, DeepSeek, Qwen,
GLM, or your own [OmniRouter](https://github.com/Godde3s/omnirouter):

```python
from baleforge.agent import AgentBridge, AgentConfig

agent = AgentBridge(AgentConfig(
    base_url="https://api.example.com/v1",
    api_key="sk-...",
    model="gpt-4o-mini",
))

@agent.tool("now", "Current date/time")
async def now() -> str:
    from datetime import datetime; return datetime.now().isoformat()

@router.message()
async def chat(ctx):
    await ctx.bot.typing(ctx.update.effective_chat_id)
    await ctx.reply(await agent.respond(ctx.update.effective_chat_id,
                                        ctx.update.message.text))
```

The bridge keeps **per-chat memory**, runs a **bounded tool-calling
loop**, trims history to a configurable budget, and never lets a failing
tool crash the bot. Persian is a first-class citizen: default prompts and
built-in fallbacks speak the user's language.

## Architecture

```
 Bale servers ⇄ BaleClient (retry, backoff)     api.py
                    │
              poll_forever()                    bot.py      long-polling loop,
                    │                                        stale-drop, error isolation
              Dispatcher ── middleware chain    dispatcher.py
              ┌───┴───┬─────────┐
          Router   Router    FSM                declarative filters + state
                    │
              AgentBridge (optional)            agent.py    tools + memory + LLM
```

## فارسی

**باله‌فورج** فریم‌ورک ساخت ربات برای پیام‌رسان بله است: کاملاً async، با
فیلترهای اعلانی، ماشین حالت، میدل‌ور و پل هوش مصنوعی (سازگار با هر
endpoint سازگار با OpenAI). نمونه‌ها در پوشه `examples/` و مستندات کامل
بالای همین صفحه — به فارسی، برای فارسی‌زبان‌ها.

## Testing

```bash
pip install -e .[dev]
pytest
```

60+ tests cover filters, FSM transitions, middleware ordering, the agent
tool loop and history trimming — all against fake transports, zero
network access.

## Roadmap

- [ ] Webhook receiver (aiohttp) alongside long polling
- [ ] Media upload helpers (photo/voice/document)
- [ ] Redis FSM storage
- [ ] Channel post support

## License

MIT © Reza Bazdar (Godde3s)

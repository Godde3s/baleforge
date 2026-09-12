"""AI assistant bot: BaleForge + any OpenAI-compatible endpoint.

Env vars:
    BALE_TOKEN      bot token from @BotFather on Bale
    AGENT_BASE_URL  e.g. https://api.openai.com/v1 (or your OmniRouter!)
    AGENT_API_KEY   secret key
    AGENT_MODEL     model name, default gpt-4o-mini

Run:  python examples/ai_agent_bot.py
"""

import asyncio
import os

from baleforge import Bot, Router, command
from baleforge.agent import AgentBridge, AgentConfig

router = Router()
agent = AgentBridge(AgentConfig(
    base_url=os.environ["AGENT_BASE_URL"],
    api_key=os.environ["AGENT_API_KEY"],
    model=os.environ.get("AGENT_MODEL", "gpt-4o-mini"),
    system_prompt=(
        "تو دستیار هوشمند ربات بله هستی. کوتاه، دقیق و دوستانه جواب بده "
        "و همیشه به زبان کاربر پاسخ بده."
    ),
))


# Give the model real capabilities — tools are plain async functions.
@agent.tool("now", "Current date and time in ISO format")
async def now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


@agent.tool("weather", "Fake weather lookup for a city (demo tool)",
            parameters={
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
            })
async def weather(city: str) -> str:
    return f"hava in {city}: 24°C, partly cloudy (demo data)"


@router.message(command("start"))
async def start(ctx):
    await ctx.reply("سلام! من یک دستیار هوشمندم — هر چی بپرسی جواب می‌دم 🤖\n/reset برای پاک‌کردن حافظه.")


@router.message(command("reset"))
async def reset(ctx):
    agent.reset(ctx.update.effective_chat_id)
    await ctx.reply("حافظه گفتگو پاک شد ✨")


@router.message()
async def chat(ctx):
    chat_id = ctx.update.effective_chat_id
    await ctx.bot.typing(chat_id)                      # show "typing..."
    answer = await agent.respond(chat_id, ctx.update.message.text)
    await ctx.reply(answer or "…")


async def main() -> None:
    bot = Bot(os.environ["BALE_TOKEN"], name="ai-agent").include(router)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os

from baleforge import Bot, InlineButton, InlineKeyboard, Router, command, text

router = Router()


@router.message(command("start"))
async def start(ctx):
    kb = InlineKeyboard.of(
        InlineButton("وضعیت سیستم", callback_data="status"),
        InlineButton("درباره من", callback_data="about"),
    )
    await ctx.reply(
        "سلام! به ربات ساخته‌شده با BaleForge خوش اومدی 🚀\n"
        "از دکمه‌های زیر استفاده کن یا /help رو بزن.",
        reply_markup=kb.to_dict(),
    )


@router.message(command("help"))
async def help_cmd(ctx):
    await ctx.reply("دستورها:\n/start — شروع\n/help — همین پیام\nهر متنی بفرست تا تکرارش کنم.")


@router.message(text(contains="سلام"))
async def greet(ctx):
    await ctx.reply("سلام علیکم! 👋")


@router.message()
async def echo(ctx):
    await ctx.reply(f"🔊 {ctx.update.message.text}")


@router.callback_query()
async def buttons(ctx):
    data = ctx.update.callback_query.data
    answers = {"status": "همه‌چیز سبز است ✅", "about": "BaleForge — فریم‌ورک ربات بله"}
    await ctx.answer_callback(answers.get(data, ""))


async def main() -> None:
    token = os.environ["BALE_TOKEN"]
    bot = Bot(token, name="echo-bot").include(router)
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())

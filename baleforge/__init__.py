"""BaleForge — a modern async framework for Bale messenger bots.

Telegram-compatible API, declarative filters, FSM, middleware, and a
first-class AI agent bridge (any OpenAI-compatible endpoint).
"""

from .api import BaleAPIError, BaleClient
from .bot import Bot
from .dispatcher import (
    Context,
    Dispatcher,
    FSM,
    Router,
    callback,
    chat_type,
    command,
    from_user,
    state,
    text,
)
from .types import Chat, InlineButton, InlineKeyboard, Message, Update, User

__version__ = "1.0.0"
__all__ = [
    "Bot", "BaleClient", "BaleAPIError", "Router", "Dispatcher", "Context",
    "FSM", "InlineKeyboard", "InlineButton", "Update", "Message", "User",
    "Chat", "command", "text", "chat_type", "from_user", "state", "callback",
    "__version__",
]

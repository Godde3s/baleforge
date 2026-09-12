"""AI agent bridge — give any Bale bot an OpenAI-compatible brain.

``AgentBridge`` keeps per-chat conversation memory, streams nothing
(Bale has no edit-stream UX guarantee, so replies arrive as full
messages), supports an optional *tool loop*: the model may call
registered Python functions and the final answer is sent back to chat.
Works with any OpenAI-compatible endpoint — OmniRouter, GLM, Qwen,
DeepSeek, OpenAI itself.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import httpx

from .types import Update

log = logging.getLogger("baleforge.agent")

ToolFn = Callable[..., Awaitable[str]]


@dataclass
class AgentConfig:
    base_url: str                       # e.g. https://api.openai.com/v1
    api_key: str
    model: str = "gpt-4o-mini"
    system_prompt: str = (
        "You are a helpful assistant inside the Bale messenger. "
        "Answer concisely, be friendly, reply in the user's language."
    )
    temperature: float = 0.4
    max_history: int = 12               # messages kept per chat
    request_timeout: float = 60.0


@dataclass
class Tool:
    name: str
    description: str
    fn: ToolFn
    parameters: dict = field(default_factory=lambda: {"type": "object", "properties": {}})


class AgentBridge:
    def __init__(self, config: AgentConfig) -> None:
        self.config = config
        self.tools: dict[str, Tool] = {}
        self._history: dict[int, list[dict]] = {}      # chat_id -> messages
        self._client = httpx.AsyncClient(timeout=config.request_timeout)

    # ---- tool registry ---------------------------------------------------

    def tool(self, name: str, description: str, parameters: dict | None = None):
        """Decorator: register an async function as a callable tool."""
        def deco(fn: ToolFn) -> ToolFn:
            self.tools[name] = Tool(
                name=name, description=description, fn=fn,
                parameters=parameters or {"type": "object", "properties": {}},
            )
            return fn
        return deco

    # ---- conversation memory ---------------------------------------------

    def _messages(self, chat_id: int) -> list[dict]:
        if chat_id not in self._history:
            self._history[chat_id] = [{"role": "system",
                                       "content": self.config.system_prompt}]
        return self._history[chat_id]

    def reset(self, chat_id: int) -> None:
        self._history.pop(chat_id, None)

    # ---- core completion ---------------------------------------------------

    async def _chat_completion(self, messages: list[dict], tools: list[dict] | None) -> dict:
        payload: dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
        }
        if tools:
            payload["tools"] = [
                {"type": "function", "function": {
                    "name": t.name, "description": t.description,
                    "parameters": t.parameters}}
                for t in self.tools.values()
            ]
        resp = await self._client.post(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def respond(self, chat_id: int, user_text: str) -> str:
        """Full agent turn: may run a tool loop, returns the final text."""
        messages = self._messages(chat_id)
        messages.append({"role": "user", "content": user_text})
        tools = list(self.tools.values()) or None

        for _ in range(6):                     # bounded tool loop
            data = await self._chat_completion(messages, tools)
            choice = data["choices"][0]
            msg = choice["message"]
            messages.append(msg)

            calls = msg.get("tool_calls") or []
            if not calls:
                self._trim(messages)
                return msg.get("content", "").strip()

            for call in calls:
                fn = call["function"]
                result = await self._run_tool(fn["name"], fn.get("arguments") or "{}")
                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": result,
                })

        return "متأسفم، نتونستم در این نوبت پاسخ مناسبی پیدا کنم."

    async def _run_tool(self, name: str, raw_args: str) -> str:
        tool = self.tools.get(name)
        if tool is None:
            return json.dumps({"error": f"unknown tool {name}"})
        try:
            args = json.loads(raw_args or "{}")
            return str(await tool.fn(**args))
        except Exception as exc:                     # never crash the bot on tools
            log.exception("tool %s failed", name)
            return json.dumps({"error": str(exc)})

    def _trim(self, messages: list[dict]) -> None:
        """Keep system + last N messages so context stays bounded."""
        budget = self.config.max_history
        if len(messages) <= budget + 1:
            return
        system = messages[0]
        rest = messages[-budget:]
        messages[:] = [system, *rest]

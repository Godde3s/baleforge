"""AgentBridge tests with a fake OpenAI-compatible server — no network."""

import json

import pytest

from baleforge.agent import AgentBridge, AgentConfig


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class FakeClient:
    """Records requests; replays scripted responses."""

    def __init__(self, script):
        self.script = list(script)
        self.requests = []

    async def post(self, url, headers=None, json=None):
        self.requests.append({"url": url, "json": json})
        return FakeResponse(self.script.pop(0))


def make_bridge(script, **cfg) -> tuple[AgentBridge, FakeClient]:
    bridge = AgentBridge(AgentConfig(
        base_url="https://fake.example/v1",
        api_key="sk-test",
        **cfg,
    ))
    fake = FakeClient(script)
    bridge._client = fake
    return bridge, fake


@pytest.mark.asyncio
async def test_plain_response_is_returned_and_history_grows():
    bridge, fake = make_bridge([{
        "choices": [{"message": {"role": "assistant", "content": "سلام!"}}],
    }])
    answer = await bridge.respond(chat_id=1, user_text="درود")
    assert answer == "سلام!"

    msgs = fake.requests[0]["json"]["messages"]
    assert msgs[0]["role"] == "system"          # system prompt injected
    assert msgs[1] == {"role": "user", "content": "درود"}

    # second turn: history is remembered
    fake.script.append({
        "choices": [{"message": {"role": "assistant", "content": "باز هم!"}}],
    })
    await bridge.respond(chat_id=1, user_text="دوباره")
    msgs2 = fake.requests[1]["json"]["messages"]
    assistants = [m for m in msgs2 if m["role"] == "assistant"]
    assert assistants and assistants[0]["content"] == "سلام!"  # kept in context


@pytest.mark.asyncio
async def test_tool_loop_executes_function_and_feeds_result():
    bridge, fake = make_bridge([
        {   # turn 1: model asks for a tool
            "choices": [{"message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "add", "arguments": '{"a": 2, "b": 3}'},
                }],
            }}],
        },
        {   # turn 2: model answers using the tool result
            "choices": [{"message": {"role": "assistant", "content": "جواب 5 است"}}],
        },
    ])

    @bridge.tool("add", "add two numbers", parameters={
        "type": "object",
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
    })
    async def add(a: float, b: float) -> str:
        return str(a + b)

    answer = await bridge.respond(chat_id=7, user_text="2+3 چنده؟")
    assert answer == "جواب 5 است"

    second = fake.requests[1]["json"]["messages"]
    tool_msg = [m for m in second if m["role"] == "tool"]
    assert tool_msg and tool_msg[0]["content"] == "5"


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_object_not_crash():
    bridge, fake = make_bridge([
        {"choices": [{"message": {
            "role": "assistant", "content": None,
            "tool_calls": [{
                "id": "c1", "type": "function",
                "function": {"name": "missing", "arguments": "{}"},
            }],
        }}]},
        {"choices": [{"message": {"role": "assistant", "content": "ok"}}]},
    ])
    answer = await bridge.respond(chat_id=1, user_text="x")
    assert answer == "ok"
    tool_msgs = [m for m in fake.requests[1]["json"]["messages"] if m["role"] == "tool"]
    assert tool_msgs and "unknown tool" in tool_msgs[0]["content"]


@pytest.mark.asyncio
async def test_history_is_trimmed_to_max_history():
    bridge, fake = make_bridge([], max_history=4)
    for i in range(10):
        fake.script.append({
            "choices": [{"message": {"role": "assistant", "content": f"reply {i}"}}],
        })
        await bridge.respond(chat_id=9, user_text=f"msg {i}")

    msgs = fake.requests[-1]["json"]["messages"]
    assert len(msgs) == 5                        # system + 4 trimmed
    assert msgs[0]["role"] == "system"


@pytest.mark.asyncio
async def test_reset_clears_chat_memory():
    bridge, fake = make_bridge([
        {"choices": [{"message": {"role": "assistant", "content": "a"}}]},
        {"choices": [{"message": {"role": "assistant", "content": "b"}}]},
    ])
    await bridge.respond(chat_id=3, user_text="one")
    bridge.reset(chat_id=3)
    await bridge.respond(chat_id=3, user_text="two")
    first_call = fake.requests[1]["json"]["messages"]
    assert [m for m in first_call if m["role"] == "user"] == [{"role": "user", "content": "two"}]

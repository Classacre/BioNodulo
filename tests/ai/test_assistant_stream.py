"""Provider stream assembly and the boundary before any tool execution."""
from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from bionodulo.ai import assistant


def chunk(*, content: str = "", reasoning: str = "", tool_calls=None, finish=None):
    return {"choices": [{"index": 0, "finish_reason": finish, "delta": {
        "content": content, "reasoning_content": reasoning, "tool_calls": tool_calls or [],
    }}]}


async def stream(*chunks):
    for item in chunks:
        yield item


def fragment(index: int, *, call_id: str = "", name: str = "", arguments: str = ""):
    return {"index": index, "id": call_id, "function": {"name": name, "arguments": arguments}}


@pytest.mark.asyncio
async def test_argument_fragments_assemble_only_after_complete_stream(monkeypatch: pytest.MonkeyPatch) -> None:
    visible: list[str] = []

    async def fake_acompletion(**_kwargs):
        return stream(
            chunk(content="I will check.", reasoning="private chain of thought", tool_calls=[
                fragment(0, call_id="c1", name="inspect", arguments='{"tar')]),
            chunk(tool_calls=[fragment(0, arguments='get":"current"}')]),
            chunk(finish="tool_calls"),
        )

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_acompletion))
    result = await assistant._call_llm(
        messages=[], provider="openai", model="test", api_key="test", api_base=None,
        temperature=0, max_tokens=100, on_text=visible.append,
    )
    assert visible == ["I will check."]
    assert result.content == "I will check."
    assert result.tool_calls == [{
        "id": "c1", "type": "function", "name": "inspect",
        "arguments": {"target": "current"}, "parse_error": "",
    }]


@pytest.mark.asyncio
async def test_truncated_tool_stream_never_runs_partial_call(monkeypatch: pytest.MonkeyPatch) -> None:
    executed: list[str] = []

    async def fake_acompletion(**_kwargs):
        return stream(chunk(tool_calls=[fragment(0, call_id="c1", name="inspect", arguments='{"tar')]))

    async def forbidden_execute(name, _arguments, _context):
        executed.append(name)
        return {}

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=fake_acompletion))
    monkeypatch.setattr(assistant, "ALL_TOOLS", [SimpleNamespace(name="inspect")])
    monkeypatch.setattr(assistant, "tool_available", lambda _name: True)
    monkeypatch.setattr(assistant, "tools_to_openai_schema", lambda _tools: [])
    monkeypatch.setattr(assistant, "aexecute_tool", forbidden_execute)
    with pytest.raises(RuntimeError, match="ended before completion"):
        await assistant.chat_with_tools("inspect", workflow=None, history=[], api_key="test", on_step=lambda _step: None)
    assert executed == []


@pytest.mark.asyncio
async def test_visible_text_is_streamed_but_provider_reasoning_is_not() -> None:
    visible: list[str] = []
    result = await assistant._collect_model_stream(stream(
        chunk(content="Hello ", reasoning="hidden thought"),
        chunk(content="there", reasoning="more hidden thought", finish="stop"),
    ), visible.append)
    assert visible == ["Hello ", "there"]
    assert result["choices"][0]["message"]["content"] == "Hello there"
    assert "hidden thought" not in str(result)


@pytest.mark.asyncio
async def test_empty_response_and_length_finish_are_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    async def empty_acompletion(**_kwargs):
        return stream(chunk(finish="stop"))

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=empty_acompletion))
    with pytest.raises(RuntimeError, match="empty response"):
        await assistant.chat_with_tools("hello", workflow=None, history=[], api_key="test", on_step=lambda _step: None)

    async def truncated_acompletion(**_kwargs):
        return stream(chunk(content="partial", finish="length"))

    monkeypatch.setitem(sys.modules, "litellm", SimpleNamespace(acompletion=truncated_acompletion))
    with pytest.raises(RuntimeError, match="could not finish"):
        await assistant.chat_with_tools("hello", workflow=None, history=[], api_key="test", on_step=lambda _step: None)

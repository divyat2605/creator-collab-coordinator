import httpx
import openai
import pytest

from agents.llm_utils import safe_json_parse, safe_score, call_json_model
from tests.fake_openai import FakeAsyncOpenAI


def _rate_limit_error():
    req = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    resp = httpx.Response(status_code=429, request=req)
    return openai.RateLimitError("rate limited", response=resp, body=None)


# ── safe_json_parse ──────────────────────────────────────────────────


def test_parses_clean_json():
    assert safe_json_parse('{"a": 1}') == {"a": 1}


def test_strips_markdown_fences():
    text = '```json\n{"a": 1}\n```'
    assert safe_json_parse(text) == {"a": 1}


def test_repairs_smart_quotes_and_python_literals():
    text = '{\u201ca\u201d: True, \u201cb\u201d: None, \u201cc\u201d: False}'
    assert safe_json_parse(text) == {"a": True, "b": None, "c": False}


def test_repairs_trailing_comma():
    text = '{"a": 1, "b": 2,}'
    assert safe_json_parse(text) == {"a": 1, "b": 2}


def test_extracts_object_from_surrounding_prose():
    text = 'Sure! Here is the JSON you asked for: {"a": 1} Hope that helps.'
    assert safe_json_parse(text) == {"a": 1}


def test_returns_error_dict_on_empty_input():
    result = safe_json_parse(None)
    assert "error" in result


def test_returns_error_dict_on_unparseable_garbage():
    result = safe_json_parse("not json at all {{{")
    assert "error" in result


def test_safe_score_handles_non_numeric():
    assert safe_score("0.85") == 0.85
    assert safe_score(None) == 0.0
    assert safe_score("not a number") == 0.0


# ── call_json_model ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_json_model_returns_parsed_response():
    client = FakeAsyncOpenAI(responder=lambda sp, up: '{"status": "ok"}')
    result = await call_json_model(
        client=client,
        model="gpt-4o-mini",
        system_prompt="sys",
        user_prompt="user",
        fallback={"status": "fallback"},
    )
    assert result == {"status": "ok"}
    assert client.calls == 1


@pytest.mark.asyncio
async def test_call_json_model_retries_then_succeeds():
    attempts = {"n": 0}

    class FlakyChatCompletions:
        async def create(self, model, messages, max_tokens=None, **kwargs):
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise _rate_limit_error()
            from tests.fake_openai import _response
            return _response('{"status": "recovered"}')

    class FlakyClient:
        def __init__(self):
            self.chat = type("C", (), {"completions": FlakyChatCompletions()})()

    result = await call_json_model(
        client=FlakyClient(),
        model="gpt-4o-mini",
        system_prompt="sys",
        user_prompt="user",
        fallback={"status": "fallback"},
        max_retries=3,
        base_delay=0.01,
    )
    assert result == {"status": "recovered"}
    assert attempts["n"] == 3


@pytest.mark.asyncio
async def test_call_json_model_falls_back_after_exhausting_retries():
    class AlwaysFailsChatCompletions:
        async def create(self, model, messages, max_tokens=None, **kwargs):
            raise _rate_limit_error()

    class AlwaysFailsClient:
        def __init__(self):
            self.chat = type("C", (), {"completions": AlwaysFailsChatCompletions()})()

    result = await call_json_model(
        client=AlwaysFailsClient(),
        model="gpt-4o-mini",
        system_prompt="sys",
        user_prompt="user",
        fallback={"status": "fallback"},
        max_retries=2,
        base_delay=0.01,
    )
    assert result["status"] == "fallback"
    assert "error" in result


@pytest.mark.asyncio
async def test_call_json_model_uses_fallback_on_malformed_output():
    client = FakeAsyncOpenAI(responder=lambda sp, up: "not valid json {{{")
    result = await call_json_model(
        client=client,
        model="gpt-4o-mini",
        system_prompt="sys",
        user_prompt="user",
        fallback={"status": "fallback"},
    )
    assert result["status"] == "fallback"
    assert "parse_error" in result

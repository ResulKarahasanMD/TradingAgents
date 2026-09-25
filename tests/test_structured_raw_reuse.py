"""A prose answer to a structured call is reused, not regenerated.

Thinking models often answer in plain text instead of calling the schema tool.
The fallback used to re-send the identical prompt, doubling that agent's latency.
"""
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from tradingagents.agents.utils.structured import bind_structured, invoke_structured_or_freetext


class Pick(BaseModel):
    rating: str


def _render(p: Pick) -> str:
    return f"rendered {p.rating}"


def _run(structured_result):
    structured, plain = MagicMock(), MagicMock()
    structured.invoke.return_value = structured_result
    plain.invoke.return_value = AIMessage(content="second call")
    out = invoke_structured_or_freetext(structured, plain, "prompt", _render, "Trader")
    return out, plain.invoke.call_count


@pytest.mark.unit
def test_parsed_result_is_rendered():
    out, plain_calls = _run({"raw": AIMessage(content=""), "parsed": Pick(rating="Hold"), "parsing_error": None})
    assert (out, plain_calls) == ("rendered Hold", 0)


@pytest.mark.unit
def test_prose_answer_is_reused_without_a_second_call():
    prose = "Hold. " + "Detailed reasoning. " * 20
    out, plain_calls = _run({"raw": AIMessage(content=prose), "parsed": None, "parsing_error": None})
    assert (out, plain_calls) == (prose, 0)


@pytest.mark.unit
def test_content_blocks_are_joined():
    blocks = [{"type": "reasoning", "text": "x"}, {"type": "text", "text": "A" * 250}]
    out, plain_calls = _run({"raw": AIMessage(content=blocks), "parsed": None, "parsing_error": None})
    assert (out, plain_calls) == ("A" * 250, 0)


@pytest.mark.unit
@pytest.mark.parametrize("stub", ["", "I'll call the tool now."])
def test_empty_or_stub_answer_still_falls_back(stub):
    out, plain_calls = _run({"raw": AIMessage(content=stub), "parsed": None, "parsing_error": ValueError("bad json")})
    assert (out, plain_calls) == ("second call", 1)


@pytest.mark.unit
def test_legacy_non_dict_result_still_works():
    assert _run(Pick(rating="Buy")) == ("rendered Buy", 0)
    assert _run(None) == ("second call", 1)


@pytest.mark.unit
def test_bind_falls_back_when_include_raw_is_rejected():
    llm = MagicMock()
    llm.with_structured_output.side_effect = [TypeError("unexpected kwarg"), "bound"]
    assert bind_structured(llm, Pick, "Trader") == "bound"

"""Opt-in concurrent analyst phase (``parallel_analysts``).

The four analysts are independent, so running them in one fan-out node cuts the
analyst phase from the sum of their wall times to the slowest one.
"""
from __future__ import annotations

import threading
import time

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolNode

from tradingagents.graph.analyst_execution import (
    MAX_ANALYST_TOOL_ROUNDS,
    PARALLEL_ANALYST_NODE,
    build_analyst_execution_plan,
    create_parallel_analyst_team,
)
from tradingagents.graph.conditional_logic import ConditionalLogic
from tradingagents.graph.setup import GraphSetup

ALL = ("market", "social", "news", "fundamentals")


@tool
def lookup(symbol: str) -> str:
    """Return a canned data row for ``symbol``."""
    return f"data for {symbol}"


def _analyst(key: str, report_key: str, *, delay: float = 0.0, seen: dict | None = None):
    """Fake analyst: one tool round, then a report that echoes the tool result."""

    def node(state):
        time.sleep(delay)
        messages = state["messages"]
        if seen is not None:
            seen[key] = [m.content for m in messages]
        if messages[-1].type != "tool":
            call = {"name": "lookup", "args": {"symbol": key}, "id": f"call-{key}"}
            return {"messages": [AIMessage(content="", tool_calls=[call])], report_key: ""}
        report = f"{key} report: {messages[-1].content}"
        return {"messages": [AIMessage(content=report)], report_key: report}

    return node


def _team(keys=ALL, **kwargs):
    plan = build_analyst_execution_plan(keys)
    nodes = {s.key: _analyst(s.key, s.report_key, **kwargs) for s in plan.specs}
    tools = {s.key: ToolNode([lookup]) for s in plan.specs}
    return plan, create_parallel_analyst_team(plan, nodes, tools)


STATE = {"messages": [HumanMessage(content="ISRG")], "company_of_interest": "ISRG"}


@pytest.mark.unit
def test_team_runs_tool_loop_and_returns_only_reports():
    plan, team = _team()
    out = team(STATE)
    assert set(out) == {s.report_key for s in plan.specs}
    assert out["market_report"] == "market report: data for market"
    assert out["sentiment_report"] == "social report: data for social"


@pytest.mark.unit
def test_analysts_do_not_see_each_others_messages():
    seen: dict = {}
    _, team = _team(seen=seen)
    team(STATE)
    for key, contents in seen.items():
        assert contents == ["ISRG", "", f"data for {key}"]


@pytest.mark.unit
def test_analysts_overlap_in_time():
    _, team = _team(delay=0.2)  # 2 LLM rounds x 0.2s each; sequential would be 1.6s
    started = time.monotonic()
    team(STATE)
    assert time.monotonic() - started < 1.0


@pytest.mark.unit
def test_analyst_failure_propagates():
    plan = build_analyst_execution_plan(("market", "news"))

    def boom(state):
        raise ValueError("provider down")

    nodes = {"market": boom, "news": _analyst("news", "news_report")}
    tools = {s.key: ToolNode([lookup]) for s in plan.specs}
    with pytest.raises(ValueError, match="provider down"):
        create_parallel_analyst_team(plan, nodes, tools)(STATE)


@pytest.mark.unit
def test_runaway_tool_loop_is_bounded():
    plan = build_analyst_execution_plan(("market", "news"))
    rounds = {"n": 0}
    lock = threading.Lock()

    def never_done(state):
        with lock:
            rounds["n"] += 1
        call = {"name": "lookup", "args": {"symbol": "x"}, "id": f"c{rounds['n']}"}
        return {"messages": [AIMessage(content="", tool_calls=[call])]}

    nodes = {"market": never_done, "news": _analyst("news", "news_report")}
    tools = {s.key: ToolNode([lookup]) for s in plan.specs}
    with pytest.raises(RuntimeError, match="tool rounds"):
        create_parallel_analyst_team(plan, nodes, tools)(STATE)
    assert rounds["n"] == MAX_ANALYST_TOOL_ROUNDS


def _graph_nodes(parallel: bool, analysts=ALL) -> set[str]:
    setup = GraphSetup(
        object(), object(), {k: ToolNode([lookup]) for k in ALL},
        ConditionalLogic(), parallel_analysts=parallel,
    )
    return set(setup.setup_graph(analysts).compile().get_graph().nodes)


@pytest.mark.unit
def test_graph_shape_default_is_sequential():
    nodes = _graph_nodes(False)
    assert PARALLEL_ANALYST_NODE not in nodes
    assert {"Market Analyst", "tools_market", "Msg Clear Market"} <= nodes


@pytest.mark.unit
def test_graph_shape_parallel_replaces_analyst_chain():
    nodes = _graph_nodes(True)
    assert PARALLEL_ANALYST_NODE in nodes
    assert not {"Market Analyst", "tools_market", "Msg Clear Market"} & nodes
    assert "Bull Researcher" in nodes


@pytest.mark.unit
def test_single_analyst_stays_sequential():
    assert PARALLEL_ANALYST_NODE not in _graph_nodes(True, analysts=("market",))


@pytest.mark.unit
def test_failing_tool_becomes_error_message_not_a_crash():
    from tradingagents.graph.analyst_execution import _run_tool_calls

    @tool
    def broken(symbol: str) -> str:
        """Always fails."""
        raise RuntimeError("vendor 500")

    calls = [
        {"name": "broken", "args": {"symbol": "x"}, "id": "a"},
        {"name": "missing_tool", "args": {}, "id": "b"},
        {"name": "lookup", "args": {"symbol": "ok"}, "id": "c"},
    ]
    out = _run_tool_calls(ToolNode([broken, lookup]), calls)
    assert [m.tool_call_id for m in out] == ["a", "b", "c"]
    assert [m.status for m in out] == ["error", "error", "success"]
    assert "vendor 500" in out[0].content
    assert out[2].content == "data for ok"

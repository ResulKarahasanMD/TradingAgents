import contextvars
from collections.abc import Callable, Iterable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from time import monotonic
from typing import Any

from langchain_core.messages import ToolMessage


@dataclass(frozen=True)
class AnalystNodeSpec:
    key: str
    agent_node: str
    clear_node: str
    tool_node: str
    report_key: str


@dataclass(frozen=True)
class AnalystExecutionPlan:
    specs: list[AnalystNodeSpec]


ANALYST_NODE_SPECS: dict[str, AnalystNodeSpec] = {
    "market": AnalystNodeSpec(
        key="market",
        agent_node="Market Analyst",
        clear_node="Msg Clear Market",
        tool_node="tools_market",
        report_key="market_report",
    ),
    "social": AnalystNodeSpec(
        # Wire key stays "social" for saved-config back-compat; the
        # user-facing label is "Sentiment Analyst" to match the rename
        # that landed in v0.2.5 (sentiment_analyst now ingests news +
        # StockTwits + Reddit, not just social media).
        key="social",
        agent_node="Sentiment Analyst",
        clear_node="Msg Clear Sentiment",
        tool_node="tools_social",
        report_key="sentiment_report",
    ),
    "news": AnalystNodeSpec(
        key="news",
        agent_node="News Analyst",
        clear_node="Msg Clear News",
        tool_node="tools_news",
        report_key="news_report",
    ),
    "fundamentals": AnalystNodeSpec(
        key="fundamentals",
        agent_node="Fundamentals Analyst",
        clear_node="Msg Clear Fundamentals",
        tool_node="tools_fundamentals",
        report_key="fundamentals_report",
    ),
}


def build_analyst_execution_plan(
    selected_analysts: Iterable[str],
) -> AnalystExecutionPlan:
    specs: list[AnalystNodeSpec] = []
    for analyst_key in selected_analysts:
        spec = ANALYST_NODE_SPECS.get(analyst_key)
        if spec is None:
            raise ValueError(f"unknown analyst key: {analyst_key}")
        specs.append(spec)

    if not specs:
        raise ValueError("at least one analyst must be selected")

    return AnalystExecutionPlan(specs=specs)


PARALLEL_ANALYST_NODE = "Analyst Team"

# Bound on one analyst's agent<->tools loop inside the team node, where the
# graph-level recursion limit cannot see the individual rounds.
MAX_ANALYST_TOOL_ROUNDS = 25


def _run_tool_calls(tool_node: Any, tool_calls: list[dict]) -> list[ToolMessage]:
    """Execute one round of tool calls against a ToolNode's registered tools.

    ToolNode.invoke() needs the LangGraph runtime of the node it is mounted on,
    which a worker thread inside another node does not have, so the tools are
    called directly. A failing or unknown tool becomes an error ToolMessage so
    the analyst can recover, rather than aborting its three siblings.
    """
    results: list[ToolMessage] = []
    for call in tool_calls:
        try:
            tool = tool_node.tools_by_name[call["name"]]
            result = tool.invoke({**call, "type": "tool_call"})
        except Exception as exc:  # noqa: BLE001 - surfaced to the model
            result = ToolMessage(
                content=f"Error: {exc!r}\n Please fix your mistakes.",
                name=call.get("name", "tool"),
                tool_call_id=call["id"],
                status="error",
            )
        results.append(result)
    return results


def _run_analyst_loop(
    spec: AnalystNodeSpec,
    analyst_node: Callable[[dict], dict],
    tool_node: Any,
    state: Mapping[str, Any],
) -> str:
    """Drive one analyst's agent<->tools loop on a private message history."""
    messages = list(state["messages"])
    for _ in range(MAX_ANALYST_TOOL_ROUNDS):
        update = analyst_node({**state, "messages": messages})
        new_messages = list(update.get("messages", []))
        messages.extend(new_messages)
        last = new_messages[-1] if new_messages else None
        if last is not None and getattr(last, "tool_calls", None):
            messages.extend(_run_tool_calls(tool_node, last.tool_calls))
            continue
        return update.get(spec.report_key, "")
    raise RuntimeError(
        f"{spec.agent_node} exceeded {MAX_ANALYST_TOOL_ROUNDS} tool rounds without a report"
    )


def create_parallel_analyst_team(
    plan: AnalystExecutionPlan,
    analyst_nodes: Mapping[str, Callable[[dict], dict]],
    tool_nodes: Mapping[str, Any],
):
    """One graph node that runs every selected analyst concurrently.

    The analysts are independent (each reads only the instrument context and
    writes only its own report), but the sequential graph serialises them on the
    shared ``messages`` channel. Here each gets a private copy of the message
    history, so wall time drops from the sum of the analysts to the slowest one.
    The work is LLM/network-bound, so threads are sufficient. Only the reports
    are written back; the shared ``messages`` channel is left untouched, which
    also makes the per-analyst "Msg Clear" nodes unnecessary.
    """

    def analyst_team_node(state):
        with ThreadPoolExecutor(
            max_workers=len(plan.specs), thread_name_prefix="analyst"
        ) as pool:
            # copy_context() carries the LangChain run config (callbacks,
            # tracing) into the worker threads.
            futures = {
                spec.report_key: pool.submit(
                    contextvars.copy_context().run,
                    _run_analyst_loop,
                    spec,
                    analyst_nodes[spec.key],
                    tool_nodes[spec.key],
                    state,
                )
                for spec in plan.specs
            }
            return {report_key: future.result() for report_key, future in futures.items()}

    return analyst_team_node


def get_initial_analyst_node(plan: AnalystExecutionPlan) -> str:
    return plan.specs[0].agent_node


class AnalystWallTimeTracker:
    def __init__(self, plan: AnalystExecutionPlan):
        self.plan = plan
        self._started_at: dict[str, float] = {}
        self._wall_times: dict[str, float] = {}

    def mark_started(self, analyst_key: str, started_at: float | None = None) -> None:
        if analyst_key not in ANALYST_NODE_SPECS:
            raise ValueError(f"unknown analyst key: {analyst_key}")
        self._started_at.setdefault(analyst_key, monotonic() if started_at is None else started_at)

    def mark_completed(
        self,
        analyst_key: str,
        completed_at: float | None = None,
    ) -> None:
        if analyst_key not in ANALYST_NODE_SPECS:
            raise ValueError(f"unknown analyst key: {analyst_key}")
        if analyst_key in self._wall_times:
            return
        started_at = self._started_at.get(analyst_key)
        if started_at is None:
            return
        finished_at = monotonic() if completed_at is None else completed_at
        self._wall_times[analyst_key] = max(0.0, finished_at - started_at)

    def get_wall_times(self) -> dict[str, float]:
        return dict(self._wall_times)

    def format_summary(self) -> str:
        parts = []
        for spec in self.plan.specs:
            duration = self._wall_times.get(spec.key)
            if duration is not None:
                label = spec.agent_node.removesuffix(" Analyst")
                parts.append(f"{label} {duration:.2f}s")
        if not parts:
            return "Analyst wall time: pending"
        return "Analyst wall time: " + " | ".join(parts)


def sync_analyst_tracker_from_chunk(
    tracker: AnalystWallTimeTracker,
    chunk: dict[str, str],
    now: float | None = None,
) -> None:
    current_time = monotonic() if now is None else now
    active_found = False

    for spec in tracker.plan.specs:
        has_report = bool(chunk.get(spec.report_key))

        if has_report:
            tracker.mark_started(spec.key, started_at=current_time)
            tracker.mark_completed(spec.key, completed_at=current_time)
            continue

        if not active_found:
            tracker.mark_started(spec.key, started_at=current_time)
            active_found = True

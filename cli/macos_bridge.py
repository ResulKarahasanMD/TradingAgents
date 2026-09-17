from __future__ import annotations

import datetime as dt
import json
import traceback
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from cli.stats_handler import StatsCallbackHandler
from cli.utils import _llm_provider_table
from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.llm_clients.model_catalog import get_model_options

load_dotenv()

app = typer.Typer(
    name="tradingagents-macos-bridge",
    help="Structured bridge used by the native macOS wrapper app.",
    add_completion=False,
)


ANALYST_ORDER = ["market", "social", "news", "fundamentals"]
ANALYST_METADATA = [
    {
        "value": "market",
        "title": "Market Analyst",
        "summary": "Technical indicators, price action, and market structure.",
    },
    {
        "value": "social",
        "title": "Social Media Analyst",
        "summary": "Social chatter and sentiment signals.",
    },
    {
        "value": "news",
        "title": "News Analyst",
        "summary": "News flow, macro events, and insider activity.",
    },
    {
        "value": "fundamentals",
        "title": "Fundamentals Analyst",
        "summary": "Financials, balance sheet, and business quality.",
    },
]
ANALYST_AGENT_NAMES = {
    "market": "Market Analyst",
    "social": "Social Analyst",
    "news": "News Analyst",
    "fundamentals": "Fundamentals Analyst",
}
ANALYST_REPORT_MAP = {
    "market": "market_report",
    "social": "sentiment_report",
    "news": "news_report",
    "fundamentals": "fundamentals_report",
}
REPORT_TITLES = {
    "market_report": "Market Analysis",
    "sentiment_report": "Social Sentiment",
    "news_report": "News Analysis",
    "fundamentals_report": "Fundamentals Analysis",
    "investment_plan": "Research Team Decision",
    "trader_investment_plan": "Trading Team Plan",
    "final_trade_decision": "Portfolio Management Decision",
}
REPORT_SECTIONS = {
    "market_report": ("market", "Market Analyst"),
    "sentiment_report": ("social", "Social Analyst"),
    "news_report": ("news", "News Analyst"),
    "fundamentals_report": ("fundamentals", "Fundamentals Analyst"),
    "investment_plan": (None, "Research Manager"),
    "trader_investment_plan": (None, "Trader"),
    "final_trade_decision": (None, "Portfolio Manager"),
}
FIXED_AGENTS = {
    "Research Team": ["Bull Researcher", "Bear Researcher", "Research Manager"],
    "Trading Team": ["Trader"],
    "Risk Management": ["Aggressive Analyst", "Neutral Analyst", "Conservative Analyst"],
    "Portfolio Management": ["Portfolio Manager"],
}
OUTPUT_LANGUAGES = [
    {"label": "English (default)", "value": "English"},
    {"label": "Chinese (中文)", "value": "Chinese"},
    {"label": "Japanese (日本語)", "value": "Japanese"},
    {"label": "Korean (한국어)", "value": "Korean"},
    {"label": "Hindi (हिन्दी)", "value": "Hindi"},
    {"label": "Spanish (Español)", "value": "Spanish"},
    {"label": "Portuguese (Português)", "value": "Portuguese"},
    {"label": "French (Français)", "value": "French"},
    {"label": "German (Deutsch)", "value": "German"},
    {"label": "Arabic (العربية)", "value": "Arabic"},
    {"label": "Russian (Русский)", "value": "Russian"},
    {"label": "Custom language", "value": "custom"},
]
RESEARCH_DEPTHS = [
    {
        "label": "Shallow",
        "value": 1,
        "summary": "Quick research with fewer debate rounds.",
    },
    {
        "label": "Medium",
        "value": 3,
        "summary": "Balanced research and debate depth.",
    },
    {
        "label": "Deep",
        "value": 5,
        "summary": "Longest, most comprehensive research path.",
    },
]
OPENAI_REASONING_EFFORTS = [
    {"label": "Medium (Default)", "value": "medium"},
    {"label": "High (More thorough)", "value": "high"},
    {"label": "Low (Faster)", "value": "low"},
]
ANTHROPIC_EFFORTS = [
    {"label": "High (recommended)", "value": "high"},
    {"label": "Medium (balanced)", "value": "medium"},
    {"label": "Low (faster, cheaper)", "value": "low"},
]
GOOGLE_THINKING_LEVELS = [
    {"label": "Enable Thinking (recommended)", "value": "high"},
    {"label": "Minimal/Disable Thinking", "value": "minimal"},
]


@dataclass
class AnalysisRequest:
    ticker: str
    analysis_date: str
    analysts: list[str]
    research_depth: int
    llm_provider: str
    backend_url: str | None
    shallow_thinker: str
    deep_thinker: str
    google_thinking_level: str | None
    openai_reasoning_effort: str | None
    anthropic_effort: str | None
    output_language: str
    results_root: str | None


class SessionTracker:
    def __init__(self, request: AnalysisRequest, session_dir: Path):
        self.request = request
        self.session_dir = session_dir
        self.live_reports_dir = session_dir / "live_reports"
        self.live_reports_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = session_dir / "message_tool.log"
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        self.log_file.touch(exist_ok=True)

        self.messages: deque[dict[str, Any]] = deque(maxlen=120)
        self.tool_calls: deque[dict[str, Any]] = deque(maxlen=120)
        self.agent_status: dict[str, str] = {}
        self.report_sections: dict[str, str | None] = {}
        self.current_report_title: str | None = None
        self.current_report_markdown: str | None = None
        self.final_report_markdown: str | None = None
        self._last_message_id: str | None = None
        self._init_state()

    def _init_state(self) -> None:
        for analyst_key in self.request.analysts:
            agent_name = ANALYST_AGENT_NAMES.get(analyst_key)
            if agent_name:
                self.agent_status[agent_name] = "pending"

        for team_agents in FIXED_AGENTS.values():
            for agent in team_agents:
                self.agent_status[agent] = "pending"

        for section_name, (analyst_key, _) in REPORT_SECTIONS.items():
            if analyst_key is None or analyst_key in self.request.analysts:
                self.report_sections[section_name] = None

        if self.request.analysts:
            first_analyst = ANALYST_AGENT_NAMES[self.request.analysts[0]]
            self.agent_status[first_analyst] = "in_progress"

    def add_message(self, kind: str, content: str) -> None:
        if not content:
            return
        entry = {
            "id": f"msg-{len(self.messages) + 1}-{dt.datetime.now().timestamp()}",
            "timestamp": dt.datetime.now().strftime("%H:%M:%S"),
            "kind": kind,
            "content": content,
        }
        self.messages.append(entry)
        with self.log_file.open("a") as handle:
            handle.write(f"{entry['timestamp']} [{kind}] {content.replace(chr(10), ' ')}\n")

    def add_tool_call(self, name: str, args: Any) -> None:
        entry = {
            "id": f"tool-{len(self.tool_calls) + 1}-{dt.datetime.now().timestamp()}",
            "timestamp": dt.datetime.now().strftime("%H:%M:%S"),
            "name": name,
            "args": args,
        }
        self.tool_calls.append(entry)
        args_str = json.dumps(args, ensure_ascii=False)
        with self.log_file.open("a") as handle:
            handle.write(f"{entry['timestamp']} [Tool Call] {name} {args_str}\n")

    def update_agent_status(self, agent: str, status: str) -> None:
        if agent in self.agent_status:
            self.agent_status[agent] = status

    def update_report_section(self, section_name: str, content: str | None) -> None:
        if section_name not in self.report_sections:
            return
        if content is None:
            return
        normalized = content.strip()
        if not normalized:
            return
        self.report_sections[section_name] = normalized
        self.current_report_title = REPORT_TITLES.get(section_name, section_name)
        self.current_report_markdown = f"### {self.current_report_title}\n{normalized}"
        (self.live_reports_dir / f"{section_name}.md").write_text(normalized)
        self._update_final_report()

    def _update_final_report(self) -> None:
        report_parts: list[str] = []

        analyst_sections = [
            ("Market Analysis", self.report_sections.get("market_report")),
            ("Social Sentiment", self.report_sections.get("sentiment_report")),
            ("News Analysis", self.report_sections.get("news_report")),
            ("Fundamentals Analysis", self.report_sections.get("fundamentals_report")),
        ]
        analyst_content = [f"### {title}\n{text}" for title, text in analyst_sections if text]
        if analyst_content:
            report_parts.append("## Analyst Team Reports\n\n" + "\n\n".join(analyst_content))

        if self.report_sections.get("investment_plan"):
            report_parts.append(
                "## Research Team Decision\n\n" + self.report_sections["investment_plan"]
            )

        if self.report_sections.get("trader_investment_plan"):
            report_parts.append(
                "## Trading Team Plan\n\n" + self.report_sections["trader_investment_plan"]
            )

        if self.report_sections.get("final_trade_decision"):
            report_parts.append(
                "## Portfolio Management Decision\n\n"
                + self.report_sections["final_trade_decision"]
            )

        self.final_report_markdown = "\n\n".join(report_parts) if report_parts else None

    def completed_reports_count(self) -> int:
        count = 0
        for section_name, (_, finalizing_agent) in REPORT_SECTIONS.items():
            if section_name not in self.report_sections:
                continue
            if self.report_sections.get(section_name) and self.agent_status.get(finalizing_agent) == "completed":
                count += 1
        return count

    def mark_all_completed(self) -> None:
        for agent in list(self.agent_status):
            self.agent_status[agent] = "completed"

    def snapshot(self, stats_handler: StatsCallbackHandler, started_at: float) -> dict[str, Any]:
        stats = stats_handler.get_stats()
        return {
            "ticker": self.request.ticker,
            "analysis_date": self.request.analysis_date,
            "agent_statuses": self.agent_status,
            "messages": list(self.messages),
            "tool_calls": list(self.tool_calls),
            "current_report_title": self.current_report_title,
            "current_report_markdown": self.current_report_markdown,
            "final_report_markdown": self.final_report_markdown,
            "reports_completed": self.completed_reports_count(),
            "reports_total": len(self.report_sections),
            "elapsed_seconds": round(dt.datetime.now().timestamp() - started_at, 1),
            "stats": stats,
        }


def _catalog_models(provider: str, mode: str) -> list[dict[str, str]]:
    try:
        options = get_model_options(provider, mode)
    except KeyError:
        return []
    return [{"label": label, "value": model} for label, model in options if model != "custom"]


def build_catalog() -> dict[str, Any]:
    providers: list[dict[str, Any]] = []
    for name, value, base_url in _llm_provider_table():
        # The app shows either a model picker or a free-text field, so the
        # CLI's "Custom model ID" entry is dropped and providers left without
        # a curated list (OpenRouter, Azure, custom-only) get the text field.
        quick_models = _catalog_models(value, "quick")
        deep_models = _catalog_models(value, "deep")
        provider_options = {
            "name": name,
            "value": value,
            "base_url": base_url,
            "supports_custom_models": not (quick_models and deep_models),
            "quick_models": quick_models,
            "deep_models": deep_models,
        }
        providers.append(provider_options)

    return {
        "default_date": dt.date.today().isoformat(),
        "default_provider": DEFAULT_CONFIG["llm_provider"],
        "default_quick_model": DEFAULT_CONFIG["quick_think_llm"],
        "default_deep_model": DEFAULT_CONFIG["deep_think_llm"],
        "default_output_language": DEFAULT_CONFIG["output_language"],
        "analysts": ANALYST_METADATA,
        "providers": providers,
        "research_depths": RESEARCH_DEPTHS,
        "output_languages": OUTPUT_LANGUAGES,
        "openai_reasoning_efforts": OPENAI_REASONING_EFFORTS,
        "anthropic_efforts": ANTHROPIC_EFFORTS,
        "google_thinking_levels": GOOGLE_THINKING_LEVELS,
    }


def emit_event(event: str, **payload: Any) -> None:
    print(json.dumps({"event": event, **payload}, ensure_ascii=False), flush=True)


def normalize_request(payload: dict[str, Any]) -> AnalysisRequest:
    ticker = str(payload["ticker"]).strip().upper()
    if not ticker:
        raise ValueError("Ticker is required.")

    analysis_date = str(payload["analysis_date"]).strip()
    trade_date = dt.datetime.strptime(analysis_date, "%Y-%m-%d").date()
    if trade_date > dt.date.today():
        raise ValueError("Analysis date cannot be in the future.")

    requested_analysts = [str(value).strip().lower() for value in payload.get("analysts", [])]
    analysts = [analyst for analyst in ANALYST_ORDER if analyst in requested_analysts]
    if not analysts:
        raise ValueError("At least one analyst must be selected.")

    research_depth = int(payload.get("research_depth", 1))
    if research_depth not in {1, 3, 5}:
        raise ValueError("Research depth must be one of 1, 3, or 5.")

    provider = str(payload.get("llm_provider", DEFAULT_CONFIG["llm_provider"])).strip().lower()
    provider_defaults = {value: base_url for _, value, base_url in _llm_provider_table()}
    if provider not in provider_defaults:
        raise ValueError(f"Unsupported provider: {provider}")

    backend_url = payload.get("backend_url") or provider_defaults[provider]
    shallow_thinker = str(payload.get("shallow_thinker", "")).strip()
    deep_thinker = str(payload.get("deep_thinker", "")).strip()
    if not shallow_thinker or not deep_thinker:
        raise ValueError("Both quick and deep thinking models must be selected.")

    output_language = str(payload.get("output_language", DEFAULT_CONFIG["output_language"])).strip()
    if not output_language:
        output_language = DEFAULT_CONFIG["output_language"]

    return AnalysisRequest(
        ticker=ticker,
        analysis_date=analysis_date,
        analysts=analysts,
        research_depth=research_depth,
        llm_provider=provider,
        backend_url=backend_url,
        shallow_thinker=shallow_thinker,
        deep_thinker=deep_thinker,
        google_thinking_level=payload.get("google_thinking_level"),
        openai_reasoning_effort=payload.get("openai_reasoning_effort"),
        anthropic_effort=payload.get("anthropic_effort"),
        output_language=output_language,
        results_root=payload.get("results_root"),
    )


def load_request(request_file: Path) -> AnalysisRequest:
    payload = json.loads(request_file.read_text())
    return normalize_request(payload)


def create_session_dir(request: AnalysisRequest) -> Path:
    results_root = Path(request.results_root or DEFAULT_CONFIG["results_dir"]).expanduser()
    if not results_root.is_absolute():
        results_root = (Path.cwd() / results_root).resolve()
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    session_dir = results_root / request.ticker / request.analysis_date / f"macos_app_{timestamp}"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def extract_content_string(content: Any) -> str | None:
    if content is None:
        return None

    if isinstance(content, str):
        return content.strip() or None

    if isinstance(content, dict):
        text = content.get("text", "")
        return text.strip() or None

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, str) and item.strip():
                text_parts.append(item.strip())
            elif isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text", "")).strip()
                if text:
                    text_parts.append(text)
        return " ".join(text_parts) or None

    text = str(content).strip()
    return text or None


def classify_message(message: Any) -> tuple[str, str | None]:
    content = extract_content_string(getattr(message, "content", None))

    if isinstance(message, HumanMessage):
        if content == "Continue":
            return ("Control", content)
        return ("User", content)

    if isinstance(message, ToolMessage):
        return ("Data", content)

    if isinstance(message, AIMessage):
        return ("Agent", content)

    return ("System", content)


def update_analyst_statuses(tracker: SessionTracker, chunk: dict[str, Any]) -> None:
    found_active = False

    for analyst_key in ANALYST_ORDER:
        if analyst_key not in tracker.request.analysts:
            continue

        agent_name = ANALYST_AGENT_NAMES[analyst_key]
        report_key = ANALYST_REPORT_MAP[analyst_key]

        if chunk.get(report_key):
            tracker.update_report_section(report_key, chunk[report_key])

        has_report = bool(tracker.report_sections.get(report_key))
        if has_report:
            tracker.update_agent_status(agent_name, "completed")
        elif not found_active:
            tracker.update_agent_status(agent_name, "in_progress")
            found_active = True
        else:
            tracker.update_agent_status(agent_name, "pending")

    if not found_active and tracker.request.analysts:
        if tracker.agent_status.get("Bull Researcher") == "pending":
            tracker.update_agent_status("Bull Researcher", "in_progress")


def save_complete_report(final_state: dict[str, Any], ticker: str, session_dir: Path) -> Path:
    sections: list[str] = []

    analyst_parts: list[tuple[str, str]] = []
    if final_state.get("market_report"):
        analyst_parts.append(("Market Analyst", final_state["market_report"]))
    if final_state.get("sentiment_report"):
        analyst_parts.append(("Social Analyst", final_state["sentiment_report"]))
    if final_state.get("news_report"):
        analyst_parts.append(("News Analyst", final_state["news_report"]))
    if final_state.get("fundamentals_report"):
        analyst_parts.append(("Fundamentals Analyst", final_state["fundamentals_report"]))
    if analyst_parts:
        content = "\n\n".join(f"### {name}\n{text}" for name, text in analyst_parts)
        sections.append(f"## I. Analyst Team Reports\n\n{content}")

    if final_state.get("investment_debate_state"):
        debate = final_state["investment_debate_state"]
        research_parts: list[tuple[str, str]] = []
        if debate.get("bull_history"):
            research_parts.append(("Bull Researcher", debate["bull_history"]))
        if debate.get("bear_history"):
            research_parts.append(("Bear Researcher", debate["bear_history"]))
        if debate.get("judge_decision"):
            research_parts.append(("Research Manager", debate["judge_decision"]))
        if research_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in research_parts)
            sections.append(f"## II. Research Team Decision\n\n{content}")

    if final_state.get("trader_investment_plan"):
        sections.append(
            "## III. Trading Team Plan\n\n"
            f"### Trader\n{final_state['trader_investment_plan']}"
        )

    if final_state.get("risk_debate_state"):
        risk = final_state["risk_debate_state"]
        risk_parts: list[tuple[str, str]] = []
        if risk.get("aggressive_history"):
            risk_parts.append(("Aggressive Analyst", risk["aggressive_history"]))
        if risk.get("conservative_history"):
            risk_parts.append(("Conservative Analyst", risk["conservative_history"]))
        if risk.get("neutral_history"):
            risk_parts.append(("Neutral Analyst", risk["neutral_history"]))
        if risk_parts:
            content = "\n\n".join(f"### {name}\n{text}" for name, text in risk_parts)
            sections.append(f"## IV. Risk Management Team Decision\n\n{content}")
        if risk.get("judge_decision"):
            sections.append(
                "## V. Portfolio Manager Decision\n\n"
                f"### Portfolio Manager\n{risk['judge_decision']}"
            )

    header = (
        f"# Trading Analysis Report: {ticker}\n\n"
        f"Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    )
    report_file = session_dir / "complete_report.md"
    report_file.write_text(header + "\n\n".join(sections))
    return report_file


def run_analysis(request: AnalysisRequest) -> tuple[dict[str, Any], Path, SessionTracker, StatsCallbackHandler]:
    started_at = dt.datetime.now().timestamp()
    session_dir = create_session_dir(request)
    tracker = SessionTracker(request, session_dir)
    stats_handler = StatsCallbackHandler()

    config = DEFAULT_CONFIG.copy()
    config["max_debate_rounds"] = request.research_depth
    config["max_risk_discuss_rounds"] = request.research_depth
    config["quick_think_llm"] = request.shallow_thinker
    config["deep_think_llm"] = request.deep_thinker
    config["backend_url"] = request.backend_url
    config["llm_provider"] = request.llm_provider
    config["google_thinking_level"] = request.google_thinking_level
    config["openai_reasoning_effort"] = request.openai_reasoning_effort
    config["anthropic_effort"] = request.anthropic_effort
    config["output_language"] = request.output_language

    graph = TradingAgentsGraph(
        request.analysts,
        config=config,
        debug=True,
        callbacks=[stats_handler],
    )

    tracker.add_message("System", f"Selected ticker: {request.ticker}")
    tracker.add_message("System", f"Analysis date: {request.analysis_date}")
    tracker.add_message("System", f"Selected analysts: {', '.join(request.analysts)}")
    emit_event("snapshot", snapshot=tracker.snapshot(stats_handler, started_at))

    init_agent_state = graph.propagator.create_initial_state(request.ticker, request.analysis_date)
    args = graph.propagator.get_graph_args(callbacks=[stats_handler])

    final_state: dict[str, Any] | None = None
    for chunk in graph.graph.stream(init_agent_state, **args):
        final_state = chunk

        if chunk.get("messages"):
            last_message = chunk["messages"][-1]
            message_id = getattr(last_message, "id", None)
            if message_id != tracker._last_message_id:
                tracker._last_message_id = message_id
                message_kind, content = classify_message(last_message)
                if content:
                    tracker.add_message(message_kind, content)

                tool_calls = getattr(last_message, "tool_calls", None) or []
                for tool_call in tool_calls:
                    if isinstance(tool_call, dict):
                        tracker.add_tool_call(tool_call.get("name", "tool"), tool_call.get("args"))
                    else:
                        tracker.add_tool_call(getattr(tool_call, "name", "tool"), getattr(tool_call, "args", {}))

        update_analyst_statuses(tracker, chunk)

        debate_state = chunk.get("investment_debate_state")
        if debate_state:
            bull_history = debate_state.get("bull_history", "").strip()
            bear_history = debate_state.get("bear_history", "").strip()
            judge_decision = debate_state.get("judge_decision", "").strip()

            if bull_history or bear_history:
                for agent in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
                    if tracker.agent_status.get(agent) == "pending":
                        tracker.update_agent_status(agent, "in_progress")

            if bull_history:
                tracker.update_report_section("investment_plan", f"### Bull Researcher Analysis\n{bull_history}")
            if bear_history:
                tracker.update_report_section("investment_plan", f"### Bear Researcher Analysis\n{bear_history}")
            if judge_decision:
                tracker.update_report_section("investment_plan", f"### Research Manager Decision\n{judge_decision}")
                for agent in ["Bull Researcher", "Bear Researcher", "Research Manager"]:
                    tracker.update_agent_status(agent, "completed")
                tracker.update_agent_status("Trader", "in_progress")

        if chunk.get("trader_investment_plan"):
            tracker.update_report_section("trader_investment_plan", chunk["trader_investment_plan"])
            tracker.update_agent_status("Trader", "completed")
            tracker.update_agent_status("Aggressive Analyst", "in_progress")

        risk_state = chunk.get("risk_debate_state")
        if risk_state:
            aggressive_history = risk_state.get("aggressive_history", "").strip()
            conservative_history = risk_state.get("conservative_history", "").strip()
            neutral_history = risk_state.get("neutral_history", "").strip()
            judge_decision = risk_state.get("judge_decision", "").strip()

            if aggressive_history:
                tracker.update_agent_status("Aggressive Analyst", "in_progress")
                tracker.update_report_section("final_trade_decision", f"### Aggressive Analyst Analysis\n{aggressive_history}")
            if conservative_history:
                tracker.update_agent_status("Conservative Analyst", "in_progress")
                tracker.update_report_section("final_trade_decision", f"### Conservative Analyst Analysis\n{conservative_history}")
            if neutral_history:
                tracker.update_agent_status("Neutral Analyst", "in_progress")
                tracker.update_report_section("final_trade_decision", f"### Neutral Analyst Analysis\n{neutral_history}")
            if judge_decision:
                tracker.update_agent_status("Portfolio Manager", "in_progress")
                tracker.update_report_section("final_trade_decision", f"### Portfolio Manager Decision\n{judge_decision}")
                for agent in [
                    "Aggressive Analyst",
                    "Conservative Analyst",
                    "Neutral Analyst",
                    "Portfolio Manager",
                ]:
                    tracker.update_agent_status(agent, "completed")

        emit_event("snapshot", snapshot=tracker.snapshot(stats_handler, started_at))

    if final_state is None:
        raise RuntimeError("The analysis ended without producing a final state.")

    decision = graph.process_signal(final_state["final_trade_decision"])
    tracker.mark_all_completed()

    for section_name in tracker.report_sections:
        if section_name in final_state and final_state[section_name]:
            tracker.update_report_section(section_name, final_state[section_name])

    tracker.add_message("System", f"Completed analysis for {request.analysis_date}")
    report_file = save_complete_report(final_state, request.ticker, session_dir)
    emit_event(
        "completed",
        snapshot=tracker.snapshot(stats_handler, started_at),
        results_directory=str(session_dir),
        report_file=str(report_file),
        decision=decision,
    )
    return final_state, report_file, tracker, stats_handler


@app.command()
def options() -> None:
    print(json.dumps(build_catalog(), ensure_ascii=False))


@app.command()
def run(request_file: Path = typer.Option(..., exists=True, readable=True, dir_okay=False)) -> None:
    try:
        request = load_request(request_file)
        run_analysis(request)
    except Exception as exc:
        emit_event(
            "error",
            message=str(exc),
            details=traceback.format_exc(),
        )
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()

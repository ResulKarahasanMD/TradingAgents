"""Configurable per-request LLM timeout.

A stalled hosted endpoint otherwise holds a run for the SDK default (600s) times
the retry budget. This adds an opt-in llm_timeout knob forwarded to every
provider chat client.
"""
from __future__ import annotations

import importlib

import pytest

import tradingagents.default_config as default_config_module
from tradingagents.graph.trading_graph import TradingAgentsGraph, _coerce_timeout


@pytest.mark.unit
@pytest.mark.parametrize("value,expected", [(30, 30.0), (0.5, 0.5), ("300", 300.0), ("12.5", 12.5)])
def test_coerce_accepts_positive_numbers_and_numeric_strings(value, expected):
    assert _coerce_timeout(value) == expected


@pytest.mark.unit
@pytest.mark.parametrize("bad", [0, -1, "-3", "nan", "inf"])
def test_coerce_rejects_non_positive_and_non_finite(bad):
    with pytest.raises(ValueError, match="> 0"):
        _coerce_timeout(bad)


@pytest.mark.unit
@pytest.mark.parametrize("bad", [True, False])
def test_coerce_rejects_booleans(bad):
    with pytest.raises(ValueError, match="boolean"):
        _coerce_timeout(bad)


@pytest.mark.unit
@pytest.mark.parametrize("bad", ["abc", None])
def test_coerce_rejects_non_numbers(bad):
    with pytest.raises(ValueError, match="number"):
        _coerce_timeout(bad)


def _bare_graph(config):
    g = object.__new__(TradingAgentsGraph)
    g.config = config
    return g


@pytest.mark.unit
def test_not_forwarded_when_unset():
    kwargs = _bare_graph({"llm_provider": "openai", "llm_timeout": None})._get_provider_kwargs()
    assert "timeout" not in kwargs


@pytest.mark.unit
@pytest.mark.parametrize("provider", ["openai", "anthropic", "google", "ollama_cloud"])
def test_forwarded_across_providers(provider):
    kwargs = _bare_graph({"llm_provider": provider, "llm_timeout": "300"})._get_provider_kwargs()
    assert kwargs["timeout"] == 300.0


@pytest.mark.unit
def test_invalid_config_value_fails_loudly():
    with pytest.raises(ValueError):
        _bare_graph({"llm_provider": "openai", "llm_timeout": 0})._get_provider_kwargs()


@pytest.mark.unit
def test_timeout_reaches_the_chat_client(monkeypatch):
    from tradingagents.llm_clients.factory import create_llm_client

    monkeypatch.setenv("OLLAMA_API_KEY", "test-key")
    llm = create_llm_client("ollama_cloud", "kimi-k3", timeout=45.0).get_llm()
    assert llm.request_timeout == 45.0


def _reload_with_env(monkeypatch, **overrides):
    for key in list(default_config_module._ENV_OVERRIDES):
        monkeypatch.delenv(key, raising=False)
    for key, val in overrides.items():
        monkeypatch.setenv(key, val)
    return importlib.reload(default_config_module)


@pytest.mark.unit
def test_default_is_none(monkeypatch):
    dc = _reload_with_env(monkeypatch)
    assert dc.DEFAULT_CONFIG["llm_timeout"] is None


@pytest.mark.unit
def test_env_override_sets_config(monkeypatch):
    dc = _reload_with_env(monkeypatch, TRADINGAGENTS_LLM_TIMEOUT="300")
    assert _coerce_timeout(dc.DEFAULT_CONFIG["llm_timeout"]) == 300.0

"""The indicator window sent to the market analyst lists trading days only.

Weekend/holiday "N/A" lines and 15-digit floats were ~60% of the payload, which
is re-sent to the model on every tool round.
"""
from unittest.mock import patch

import pytest

from tradingagents.dataflows import y_finance


@pytest.mark.unit
def test_window_omits_non_trading_days_and_rounds_values():
    bars = {
        "2026-09-16": "374.48479919433595",
        "2026-09-15": "-3.0",
        "2026-09-11": "N/A",  # bar exists, indicator still warming up
    }
    with patch.object(y_finance, "_get_stock_stats_bulk", return_value=bars):
        out = y_finance.get_stock_stats_indicators_window("ISRG", "macd", "2026-09-16", 7)

    assert "2026-09-16: 374.4848\n" in out
    assert "2026-09-15: -3\n" in out
    assert "2026-09-11: N/A\n" in out
    assert "2026-09-13" not in out and "2026-09-12" not in out  # weekend
    assert "Not a trading day" not in out
    assert "non-trading days" in out  # the omission is stated once
    assert "MACD:" in out  # indicator guidance is kept

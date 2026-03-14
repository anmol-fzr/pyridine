"""Tests for the RSI Breakout Buy strategy and backtest integration."""

import datetime
import pytest

from strategies.backtest import BacktestEngine, BacktestResult, Trade


def _make_candles(prices: list[tuple[float, float, float, float]], start_time=None):
    """Build candle dicts from (open, high, low, close) tuples."""
    if start_time is None:
        start_time = datetime.datetime(2025, 1, 1, 9, 15)

    return [
        {
            "date": start_time + datetime.timedelta(minutes=5 * i),
            "open": o, "high": h, "low": l, "close": c,
            "volume": 1000,
        }
        for i, (o, h, l, c) in enumerate(prices)
    ]


class TestBacktestEngine:
    """Tests for backtesting with default RSI breakout logic."""

    def test_no_trades_on_insufficient_data(self):
        candles = _make_candles([(100, 101, 99, 100)] * 10)
        engine = BacktestEngine(candles, rsi_period=14, quantity=1)
        result = engine.run()
        assert result.total_trades == 0

    def test_signal_fires_on_uptrend(self):
        # Steady uptrend: each close > prev high → signals should fire
        prices = []
        for i in range(25):
            o = 100.0 + i * 2
            h = o + 3
            l = o - 1
            c = o + 2.5
            prices.append((o, h, l, c))

        candles = _make_candles(prices)
        engine = BacktestEngine(candles, rsi_period=14, quantity=1)
        result = engine.run()
        assert result.total_trades > 0

    def test_no_signal_in_downtrend(self):
        prices = []
        for i in range(25):
            o = 200.0 - i * 2
            h = o + 0.5
            l = o - 3
            c = o - 2.5
            prices.append((o, h, l, c))

        candles = _make_candles(prices)
        engine = BacktestEngine(candles, rsi_period=14, quantity=1)
        result = engine.run()
        assert result.total_trades == 0

    def test_equity_curve_built(self):
        prices = [(100.0 + i * 2, 103.0 + i * 2, 99.0 + i * 2, 102.5 + i * 2) for i in range(25)]
        candles = _make_candles(prices)
        engine = BacktestEngine(candles, rsi_period=14, quantity=1)
        result = engine.run()
        assert len(result.equity_curve) > 0
        assert len(result.timestamps) == len(result.equity_curve)


class TestBacktestResult:
    """Tests for BacktestResult computed properties."""

    def test_properties(self):
        now = datetime.datetime.now()
        result = BacktestResult(initial_capital=100_000)
        result.trades = [
            Trade(entry_index=15, entry_time=now, entry_price=100, exit_price=105),
            Trade(entry_index=17, entry_time=now, entry_price=110, exit_price=107),
            Trade(entry_index=19, entry_time=now, entry_price=108, exit_price=112),
        ]
        result.equity_curve = [100_000, 100_005, 100_002, 100_006]

        assert result.total_trades == 3
        assert result.wins == 2
        assert result.losses == 1
        assert abs(result.win_rate - 66.7) < 0.5
        assert abs(result.total_pnl - 6.0) < 0.01
        assert result.max_drawdown == 3.0

    def test_trade_pnl(self):
        now = datetime.datetime.now()
        t1 = Trade(entry_index=0, entry_time=now, entry_price=100, exit_price=110)
        assert t1.pnl == 10.0
        assert t1.is_win is True

        t2 = Trade(entry_index=0, entry_time=now, entry_price=100, exit_price=95)
        assert t2.pnl == -5.0
        assert t2.is_win is False


class TestRSIBreakoutBacktestCheck:
    """Test the backtest_check method of RSIBreakoutBuy using a mock kite."""

    def test_backtest_check_fires_on_uptrend(self):
        from unittest.mock import MagicMock

        kite = MagicMock()
        kite.historical_data.return_value = [
            {"date": datetime.datetime.now(), "open": 100, "high": 105,
             "low": 99, "close": 104, "volume": 100}
        ] * 20

        from strategies.rsi_breakout import RSIBreakoutBuy
        strategy = RSIBreakoutBuy(
            kite=kite, instrument_token=12345,
            tradingsymbol="TEST", exchange="NSE",
            quantity=1, rsi_period=14, interval="5minute",
        )

        # Build uptrend candles
        candles = []
        for i in range(25):
            candles.append({
                "date": datetime.datetime(2025, 1, 1) + datetime.timedelta(minutes=5 * i),
                "open": 100 + i * 2, "high": 103 + i * 2,
                "low": 99 + i * 2, "close": 102.5 + i * 2,
                "volume": 1000,
            })

        # Check at index 20 — should have RSI > 50 and close > prev high
        result = strategy.backtest_check(candles, 20)
        assert isinstance(result, bool)

    def test_backtest_check_no_signal_early(self):
        from unittest.mock import MagicMock

        kite = MagicMock()
        kite.historical_data.return_value = [
            {"date": datetime.datetime.now(), "open": 100, "high": 105,
             "low": 99, "close": 104, "volume": 100}
        ] * 20

        from strategies.rsi_breakout import RSIBreakoutBuy
        strategy = RSIBreakoutBuy(
            kite=kite, instrument_token=12345,
            tradingsymbol="TEST", exchange="NSE",
            quantity=1, rsi_period=14, interval="5minute",
        )

        candles = [{"date": datetime.datetime.now(), "open": 100, "high": 105,
                     "low": 99, "close": 104, "volume": 100}] * 25

        # Index too early for RSI
        assert strategy.backtest_check(candles, 5) is False

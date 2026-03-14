"""Tests for the StrategyEngine dispatch logic."""

import datetime
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from strategies.base import Strategy
from strategies.engine import StrategyEngine


class FakeStrategy(Strategy):
    """Minimal concrete Strategy for testing dispatch."""

    @property
    def name(self) -> str:
        return "Fake"

    def __init__(self, instrument_token: int, tradingsymbol: str, exchange: str = "NSE"):
        # Skip super().__init__ to avoid needing a kite object
        self.kite = None
        self.instrument_token = instrument_token
        self.tradingsymbol = tradingsymbol
        self.exchange = exchange
        self.quantity = 1
        self.params = {}

        self.tick_log: list[float] = []
        self.buy_log: list[float] = []
        self._should_signal = False

    def on_tick(self, last_price: float) -> bool:
        self.tick_log.append(last_price)
        return self._should_signal

    def refresh_candles(self) -> None:
        pass

    def execute_buy(self, last_price: float) -> str | None:
        self.buy_log.append(last_price)
        return "FAKE_ORDER_123"

    def backtest_check(self, candles, index) -> bool:
        return False


class TestStrategyEngineDispatch:
    """Test that on_ticks dispatches to the correct strategies."""

    def test_ticks_dispatched_to_correct_strategy(self):
        s1 = FakeStrategy(instrument_token=1001, tradingsymbol="AAA")
        s2 = FakeStrategy(instrument_token=2002, tradingsymbol="BBB")

        engine = StrategyEngine(kite=MagicMock(), strategies=[s1, s2])

        # Simulate ticks
        ticks = [
            {"instrument_token": 1001, "last_price": 100.0},
            {"instrument_token": 2002, "last_price": 200.0},
            {"instrument_token": 1001, "last_price": 101.0},
        ]

        for tick in ticks:
            for strategy in engine._dispatch.get(tick["instrument_token"], []):
                if strategy.on_tick(tick["last_price"]):
                    strategy.execute_buy(tick["last_price"])

        assert s1.tick_log == [100.0, 101.0]
        assert s2.tick_log == [200.0]

    def test_multiple_strategies_same_instrument(self):
        s1 = FakeStrategy(instrument_token=1001, tradingsymbol="AAA")
        s2 = FakeStrategy(instrument_token=1001, tradingsymbol="AAA")

        engine = StrategyEngine(kite=MagicMock(), strategies=[s1, s2])

        tick = {"instrument_token": 1001, "last_price": 150.0}
        for strategy in engine._dispatch.get(tick["instrument_token"], []):
            strategy.on_tick(tick["last_price"])

        # Both strategies received the tick
        assert s1.tick_log == [150.0]
        assert s2.tick_log == [150.0]

    def test_buy_executed_on_signal(self):
        s1 = FakeStrategy(instrument_token=1001, tradingsymbol="AAA")
        s1._should_signal = True

        engine = StrategyEngine(kite=MagicMock(), strategies=[s1])

        tick = {"instrument_token": 1001, "last_price": 500.0}
        for strategy in engine._dispatch.get(tick["instrument_token"], []):
            if strategy.on_tick(tick["last_price"]):
                strategy.execute_buy(tick["last_price"])

        assert s1.buy_log == [500.0]

    def test_no_buy_when_no_signal(self):
        s1 = FakeStrategy(instrument_token=1001, tradingsymbol="AAA")
        s1._should_signal = False

        engine = StrategyEngine(kite=MagicMock(), strategies=[s1])

        tick = {"instrument_token": 1001, "last_price": 500.0}
        for strategy in engine._dispatch.get(tick["instrument_token"], []):
            if strategy.on_tick(tick["last_price"]):
                strategy.execute_buy(tick["last_price"])

        assert s1.buy_log == []

    def test_unknown_token_ignored(self):
        s1 = FakeStrategy(instrument_token=1001, tradingsymbol="AAA")

        engine = StrategyEngine(kite=MagicMock(), strategies=[s1])

        tick = {"instrument_token": 9999, "last_price": 999.0}
        dispatched = engine._dispatch.get(tick["instrument_token"], [])
        assert dispatched == []

    def test_engine_token_set(self):
        s1 = FakeStrategy(instrument_token=1001, tradingsymbol="AAA")
        s2 = FakeStrategy(instrument_token=2002, tradingsymbol="BBB")
        s3 = FakeStrategy(instrument_token=1001, tradingsymbol="AAA")

        engine = StrategyEngine(kite=MagicMock(), strategies=[s1, s2, s3])

        assert set(engine._tokens) == {1001, 2002}

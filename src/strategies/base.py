"""
Strategy base class — all trading strategies must implement this interface.
"""

from abc import ABC, abstractmethod
import datetime
import logging

log = logging.getLogger(__name__)


class Strategy(ABC):
    """
    Abstract base class for trading strategies.

    Each strategy instance is bound to a single instrument.
    Multiple instances of the same strategy can run on different instruments.
    """

    def __init__(
        self,
        kite,
        instrument_token: int,
        tradingsymbol: str,
        exchange: str,
        quantity: int = 1,
        **params,
    ):
        self.kite = kite
        self.instrument_token = instrument_token
        self.tradingsymbol = tradingsymbol
        self.exchange = exchange
        self.quantity = quantity
        
        session_start_config = params.get("session_start") or {}
        session_end_config = params.get("session_end") or {}

        self.session_start = datetime.time(
            session_start_config.get("hour", 9),
            session_start_config.get("minute", 30),
            session_start_config.get("second", 0),
        )

        self.session_end = datetime.time(
            session_end_config.get("hour", 15),
            session_end_config.get("minute", 0),
            session_end_config.get("second", 0),
        )

        self.params = params
        self.latest_candle: dict | None = None

    def in_session(self, check_time: datetime.time | None = None) -> bool:
        """
        Return True if the specified time (or current time) is within the allowed trading window.
        By default, the market trading window logic restricts trading between 09:30 and 15:00.
        """
        current_time = check_time or datetime.datetime.now().time()
        return self.session_start <= current_time <= self.session_end

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable strategy name (e.g. 'RSI Breakout')."""
        ...

    @property
    def label(self) -> str:
        """Unique label for this instance: strategy_name:EXCHANGE:SYMBOL."""
        return f"{self.name}:{self.exchange}:{self.tradingsymbol}"

    @abstractmethod
    def on_tick(self, last_price: float) -> bool:
        """
        Called on every incoming tick for this instrument.

        Returns True if a buy signal fires.
        """
        ...

    @abstractmethod
    def refresh_candles(self) -> None:
        """
        Re-fetch historical data and update internal state.
        Called periodically by the engine when a new candle forms.
        """
        ...

    @abstractmethod
    def execute_buy(self, last_price: float) -> str | None:
        """
        Place the buy order.

        Returns order_id on success, None on failure.
        """
        ...

    @abstractmethod
    def backtest_check(self, candles: list[dict], index: int) -> bool:
        """
        Check if a buy signal would have fired at candle[index],
        given all candles up to that point.

        Used by the backtesting engine.
        """
        ...

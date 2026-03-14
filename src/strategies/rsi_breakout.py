"""
RSI Breakout Buy Strategy.

Buy signal: RSI(period) > 50 AND current tick price > previous candle's high.
Only BUY is implemented — no sell logic.
"""

import datetime
import logging

from strategies.base import Strategy
from config.loader import register_strategy
from utils.indicators import compute_rsi

log = logging.getLogger(__name__)


@register_strategy("rsi_breakout")
class RSIBreakoutBuy(Strategy):
    """
    Monitors live ticks and fires a BUY signal when:
      1. RSI (computed from recent historical closes) > 50
      2. The current tick's last_price > previous completed candle's high

    One buy per signal — a cooldown flag prevents duplicate orders
    until candles are refreshed.
    """

    @property
    def name(self) -> str:
        return "RSI Breakout"

    def __init__(
        self,
        kite,
        instrument_token: int,
        tradingsymbol: str,
        exchange: str,
        quantity: int = 1,
        rsi_period: int = 14,
        interval: str = "5minute",
        **params,
    ):
        super().__init__(
            kite=kite,
            instrument_token=instrument_token,
            tradingsymbol=tradingsymbol,
            exchange=exchange,
            quantity=quantity,
            rsi_period=rsi_period,
            interval=interval,
            **params,
        )
        self.rsi_period = int(rsi_period)
        self.interval = interval

        # Internal state
        self._signal_fired = False
        self._prev_candle_high: float | None = None
        self._closes: list[float] = []

        # Load initial historical data
        self._load_history()

    def _load_history(self):
        """Fetch recent historical candles and seed RSI closes + prev candle high."""
        now = datetime.datetime.now()
        from_date = now - datetime.timedelta(days=5)

        candles = self.kite.historical_data(
            instrument_token=self.instrument_token,
            from_date=from_date,
            to_date=now,
            interval=self.interval,
        )

        if len(candles) < self.rsi_period + 2:
            log.warning(
                "[%s] Only %d candles available, need at least %d for RSI(%d).",
                self.label, len(candles), self.rsi_period + 2, self.rsi_period,
            )

        self._closes = [c["close"] for c in candles]

        if len(candles) >= 2:
            self._prev_candle_high = candles[-2]["high"]
            log.info(
                "[%s] Loaded %d candles. Prev candle high: %.2f",
                self.label, len(candles), self._prev_candle_high,
            )
        else:
            self._prev_candle_high = None
            log.warning("[%s] Not enough candles for prev candle high.", self.label)

    def refresh_candles(self) -> None:
        """Re-fetch candles to pick up newly completed candles."""
        self._load_history()
        self._signal_fired = False

    def on_tick(self, last_price: float) -> bool:
        """
        Check if the buy signal conditions are met.

        Returns True if RSI > 50, price > prev high, and signal hasn't fired.
        """
        if self._signal_fired:
            return False

        if self._prev_candle_high is None:
            return False

        if len(self._closes) < self.rsi_period + 1:
            return False

        rsi = compute_rsi(self._closes, self.rsi_period)

        if rsi <= 50:
            log.debug("[%s] RSI=%.2f (≤50) — no signal.", self.label, rsi)
            return False

        if last_price <= self._prev_candle_high:
            log.debug(
                "[%s] Price %.2f ≤ prev high %.2f — no signal.",
                self.label, last_price, self._prev_candle_high,
            )
            return False

        log.info(
            "[%s] 🟢 BUY SIGNAL: RSI=%.2f (>50), price=%.2f > prev_high=%.2f",
            self.label, rsi, last_price, self._prev_candle_high,
        )
        return True

    def execute_buy(self, last_price: float) -> str | None:
        """Place a market buy order and set cooldown."""
        self._signal_fired = True

        try:
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.exchange,
                tradingsymbol=self.tradingsymbol,
                transaction_type=self.kite.TRANSACTION_TYPE_BUY,
                quantity=self.quantity,
                product=self.kite.PRODUCT_CNC,
                order_type=self.kite.ORDER_TYPE_MARKET,
                tag="rsi_breakout",
            )
            log.info(
                "[%s] ✅ BUY ORDER — id=%s, qty=%d, price≈%.2f",
                self.label, order_id, self.quantity, last_price,
            )
            return order_id
        except Exception as e:
            log.error("[%s] ❌ Order failed: %s", self.label, e)
            return None

    def backtest_check(self, candles: list[dict], index: int) -> bool:
        """
        Check if a buy signal would fire at candles[index].

        Uses closes up to candles[index] for RSI, and
        candles[index-1]['high'] as the previous candle high.
        """
        if index < self.rsi_period + 1:
            return False

        if index < 1:
            return False

        closes = [c["close"] for c in candles[: index + 1]]
        rsi = compute_rsi(closes, self.rsi_period)

        prev_high = candles[index - 1]["high"]
        current_close = candles[index]["close"]

        return rsi > 50 and current_close > prev_high

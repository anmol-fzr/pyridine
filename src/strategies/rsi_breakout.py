"""
RSI Breakout Buy Strategy.

Buy signal: RSI crosses ABOVE 50
Entry: Next candle breaks above the HIGH of the signal candle
Stop Loss: LOW of the signal candle
Target: Entry + (High_signal - Low_signal) * 2
Only BUY is implemented.
"""

import datetime
import logging

from strategies.base import Strategy
from config.loader import register_strategy
from utils.indicators import compute_rsi_series

log = logging.getLogger(__name__)

@register_strategy("rsi_breakout")
class RSIBreakoutBuy(Strategy):
    """
    RSI-50 Crossover Intraday Strategy — Kite Connect

    Strategy Logic:
      - Timeframe  : 5-minute candles
      - Signal     : RSI crosses ABOVE 50
      - Entry      : Next candle breaks above the HIGH of the signal candle
      - Stop Loss  : LOW of the signal candle
      - Target     : Entry + (High_signal - Low_signal) * 2
      - Session    : 09:30 AM – 03:00 PM IST (handled by base)
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
        self._signal_candle: dict | None = None
        self._waiting_entry: bool = False
        self._trade_taken: bool = False
        self._last_date: datetime.date | None = None

        # Load initial historical data
        self._load_history()

    def _load_history(self):
        """Fetch historical candles and check for RSI crossover signal."""
        now = datetime.datetime.now()
        # Fetch up to 5 days to get enough data for RSI
        from_date = now - datetime.timedelta(days=5)

        try:
            candles = self.kite.historical_data(
                instrument_token=self.instrument_token,
                from_date=from_date,
                to_date=now,
                interval=self.interval,
            )
        except Exception as e:
            log.error("[%s] Failed to fetch historical data: %s", self.label, e)
            return

        if not candles:
            return

        # Keep track of current day to reset state if it's a new day
        latest_date = candles[-1]["date"].date()
        if self._last_date is not None and self._last_date != latest_date:
            log.info("[%s] New session detected (%s), resetting state.", self.label, latest_date)
            self._trade_taken = False
            self._waiting_entry = False
            self._signal_candle = None
            
        self._last_date = latest_date

        # Drop the still-forming (current) candle — keep only completed ones
        completed_candles = candles[:-1]

        if len(completed_candles) < self.rsi_period + 2:
            log.warning(
                "[%s] Only %d completed candles available, need at least %d.",
                self.label, len(completed_candles), self.rsi_period + 2
            )
            return

        closes = [c["close"] for c in completed_candles]
        
        try:
            rsi_series = compute_rsi_series(closes, self.rsi_period)
        except ValueError as e:
            log.error("[%s] RSI computation error: %s", self.label, e)
            return

        if len(rsi_series) >= 2:
            prev_rsi = rsi_series[-2]
            curr_rsi = rsi_series[-1]

            latest_completed_candle = completed_candles[-1]

            # Check for RSI passing above 50 on the LATEST completed candle
            if prev_rsi < 50 <= curr_rsi:
                if not self._waiting_entry and not self._trade_taken:
                    self._signal_candle = latest_completed_candle
                    self._waiting_entry = True
                    log.info(
                        "[%s] ✅ RSI crossed 50 -> Signal candle recorded. H=%.2f, L=%.2f, C=%.2f, time=%s",
                        self.label, self._signal_candle["high"], self._signal_candle["low"], 
                        self._signal_candle["close"], self._signal_candle["date"]
                    )

    def refresh_candles(self) -> None:
        """Re-fetch candles to pick up newly completed candles."""
        self._load_history()

    def on_tick(self, last_price: float) -> bool:
        """
        Check if the buy signal conditions are met.

        Returns True if signal candle high is broken and we are awaiting entry.
        """
        if self._trade_taken:
            return False

        if not self._waiting_entry or not self._signal_candle:
            return False

        if last_price > self._signal_candle["high"]:
            log.info(
                "[%s] 🚀 Entry triggered! Current %.2f > Signal H=%.2f",
                self.label, last_price, self._signal_candle["high"]
            )
            return True

        return False

    def execute_buy(self, last_price: float) -> str | None:
        """Place a limit order with SL and target logic."""
        if not self._signal_candle:
            return None

        self._trade_taken = True
        self._waiting_entry = False

        entry_price = self._signal_candle["high"] + 0.05
        stop_loss = self._signal_candle["low"]
        risk = self._signal_candle["high"] - self._signal_candle["low"]
        target = entry_price + (risk * 2)

        try:
            order_id = self.kite.place_order(
                variety=self.kite.VARIETY_REGULAR,
                exchange=self.exchange,
                tradingsymbol=self.tradingsymbol,
                transaction_type=self.kite.TRANSACTION_TYPE_BUY,
                quantity=self.quantity,
                product=self.kite.PRODUCT_MIS,
                order_type=self.kite.ORDER_TYPE_LIMIT,
                price=round(entry_price, 2),
                tag="rsi_breakout",
            )
            log.info(
                "[%s] ✅ BUY ORDER — Entry=%.2f, SL=%.2f, Target=%.2f, Qty=%d, ID=%s",
                self.label, entry_price, stop_loss, target, self.quantity, order_id
            )
            return order_id
        except Exception as e:
            log.error("[%s] ❌ Order failed: %s", self.label, e)
            return None

    def backtest_check(self, candles: list[dict], index: int) -> bool:
        """
        Check if a buy signal would have fired at candles[index],
        given all candles up to that point.
        """
        if index < self.rsi_period + 2:
            return False

        current_candle = candles[index]
        current_date = current_candle["date"].date()

        closes = [c["close"] for c in candles[: index]]
        try:
            rsi_series = compute_rsi_series(closes, self.rsi_period)
        except ValueError:
            return False
            
        if len(rsi_series) < 2:
            return False

        # Traverse backwards to find the latest crossover within the same day
        idx = index - 1
        while idx >= self.rsi_period + 1 and candles[idx]["date"].date() == current_date:
            rsi_idx = len(rsi_series) - 1 - (index - 1 - idx)
            
            if rsi_idx < 1:
                break
                
            c_rsi = rsi_series[rsi_idx]
            p_rsi = rsi_series[rsi_idx - 1]
            
            if p_rsi < 50 <= c_rsi:
                signal_candle = candles[idx]
                
                # Check if high was broken in any intermediate candle
                broken_earlier = any(candles[k]["high"] > signal_candle["high"] for k in range(idx + 1, index))
                
                if not broken_earlier:
                    if current_candle["high"] > signal_candle["high"]:
                        return True
                
                # Stop looking since this is the most recent crossover
                break
                
            idx -= 1

        return False

from modules.strategy.base import Candle, Signal, Strategy
import logging


class MovingAverageStrategy(Strategy):
    def __init__(self, short: int, long: int):
        self.name = "Moving Average"
        self.short = short
        self.long = long
        self._logger = logging.getLogger(f" [{self.name}] ")
        self._logger.info(" Initialized")

    def on_candles(self, candles: list[Candle]) -> Signal:
        if len(candles) < self.long:
            return Signal.HOLD

        short_ma = sum(c.close for c in candles[-self.short:]) / self.short
        long_ma = sum(c.close for c in candles[-self.long:]) / self.long

        if short_ma > long_ma:
            return Signal.BUY
        elif short_ma < long_ma:
            return Signal.SELL

        return Signal.HOLD

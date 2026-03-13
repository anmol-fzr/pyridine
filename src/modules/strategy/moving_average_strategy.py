from modules.strategy.base import Signal, Strategy

class MovingAverageStrategy(Strategy):
    def __init__(self):
        self.prices = []

    def on_candle(self, candle):
        close = candle.close

        self.prices.append(close)

        if len(self.prices) < 20:
            return Signal.HOLD

        sma = sum(self.prices[-20:]) / 20

        if close > sma:
            return Signal.BUY

        elif close < sma:
            return Signal.SELL

        return Signal.HOLD

from modules.strategy.base import Candle, Signal, Strategy

class Backtester:
    def __init__(self, strategy: Strategy):
        self.strategy = strategy
        self.position = None
        self.trades = []

    def run(self, candles: list[Candle]):
        for candle in candles:
            print(candle)

            signal = self.strategy.on_candle(candle)
            print(signal)


            if signal == Signal.BUY and self.position is None:
                self.position = candle.close

            elif signal == Signal.SELL and self.position is not None:
                profit = candle.close - self.position

                self.trades.append({
                    "buy_price": self.position,
                    "sell_price": candle.close,
                    "profit": profit,
                    "time": candle.time
                })

                self.position = None

    def get_results(self):
        return self.trades

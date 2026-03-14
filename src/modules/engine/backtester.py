from modules.strategy.base import Candle, Signal, Strategy, Trade
import logging

logger = logging.getLogger(" [BACKTESTER] ")

class Backtester:
    def __init__(self, strategy: Strategy):
        self.strategy = strategy
        self.candles: list[Candle] = []
        self.trades: list[Trade] = []
        self.position_price: float | None = None
        logger.info(f" {strategy.name} Initialized")

    def run(self, candles: list[Candle]):
        self.candles = candles

        for candle in candles:
            signal = self.strategy.on_candles(self.candles)

            if signal == Signal.BUY and self.position_price is None:
                self.position_price = candle.close

            elif signal == Signal.SELL and self.position_price is not None:
                profit = candle.close - self.position_price

                trade = Trade(
                    time=candle.time,
                    buy_price=self.position_price,
                    less_price=candle.close,
                    profit=profit
                )

                self.trades.append(trade)

                self.position_price = None

    def get_results(self):
         return self.trades

    def __del__(self):
        logger.info(f" {self.strategy.name} Finished")

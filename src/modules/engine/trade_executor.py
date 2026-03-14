from kiteconnect import KiteConnect
from modules.strategy.base import Candle, Signal, Strategy, Trade
import logging

logger = logging.getLogger(" [TRADE EXECUTOR] ")

class TradeExecutor:
    def __init__(self, strategy: Strategy, kite: KiteConnect):
        self.strategy = strategy
        self.kite = kite
        self.trades: list[Trade] = []
        self.position_price: float | None = None
        logger.info(f" {strategy.name} Initialized")

    def _buy(self):
        return self.kite.place_order(
            variety=self.kite.VARIETY_REGULAR,
            exchange=self.kite.EXCHANGE_NSE,
            tradingsymbol="RELIANCE",
            transaction_type=self.kite.TRANSACTION_TYPE_BUY,
            quantity=1,
            product=self.kite.PRODUCT_MIS,
            order_type=self.kite.ORDER_TYPE_MARKET
        )

    def _sell(self):
        return self.kite.place_order(
            variety=self.kite.VARIETY_REGULAR,
            exchange=self.kite.EXCHANGE_NSE,
            tradingsymbol="RELIANCE",
            transaction_type=self.kite.TRANSACTION_TYPE_SELL,
            quantity=1,
            product=self.kite.PRODUCT_MIS,
            order_type=self.kite.ORDER_TYPE_MARKET
        )

    def run(self, candles: list[Candle]):
        for i, candle in enumerate(candles):
            history = candles[: i + 1]
            signal = self.strategy.on_candles(history)

            if signal == Signal.BUY and self.position_price is None:
                order_id = self._buy()
                logger.info(" Buy Order: ", order_id)

                self.position_price = candle.close

            elif signal == Signal.SELL and self.position_price is not None:
                order_id = self._sell()
                logger.info(" Sell Order: ", order_id)

                profit = candle.close - self.position_price

                self.trades.append(
                    Trade(
                        time=candle.time,
                        buy_price=self.position_price,
                        less_price=candle.close,
                        profit=profit
                    )
                )

                self.position_price = None

    def get_results(self):
        return self.trades

    def __del__(self):
        logger.info(f" {self.strategy.name} Finished")

from kiteconnect import KiteConnect
from modules.engine.backtester import Backtester
from modules.strategy.base import Candle
from modules.strategy.moving_average_strategy import MovingAverageStrategy

def MovingAverageStrategyTester(kite: KiteConnect): 
    bt = Backtester(MovingAverageStrategy())
    historical_data = kite.historical_data(
        instrument_token = "408065",
        from_date="2026-01-01 00:00:00",
        to_date="2026-02-01 00:00:00",
        interval="5minute"
    )

    candles = [
        Candle(
            time=row["date"],
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
        )
        for row in historical_data
    ]

    bt.run(candles)

    results = bt.get_results()

    return results

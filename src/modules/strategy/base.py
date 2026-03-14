from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod

class Signal(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"

@dataclass
class Trade:
    time: str  # "2026-01-01 09:15:00+05:30"
    buy_price: float
    less_price: float
    profit: float

# date, open, high, low, close, volume
# 2026-01-01 09:15:00+05:30, 1615.4, 1619.7, 1614.1, 1618.3, 30758

@dataclass
class Candle:
    time: str  # "2026-01-01 09:15:00+05:30"
    open: float
    high: float
    low: float
    close: float
    volume: float

class Strategy(ABC):
    name: str

    @abstractmethod
    def on_candles(self, candles: list[Candle]) -> Signal:
        raise NotImplementedError

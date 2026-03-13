# Pyridine

just a standard algorithmic trading pipeline using kiteconnect having 

- Strategy definition
- Backtesting engine
- Performance metrics
- Paper trading
- Live trading execution

## Core Components
| Component      | Responsibility                   |
| -------------- | -------------------------------- |
| Strategy       | decides buy/sell/hold            |
| Backtester     | runs strategy on historical data |
| Trade executor | sends orders via Kite            |
| Data provider  | provides candles/ticks           |
| Risk manager   | stop loss / target               |
| Logger         | records trades                   |

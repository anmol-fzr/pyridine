"""
RSI-50 Crossover Backtest
=========================
Strategy Logic:
- 5-minute candles
- RSI crosses above 50 → Signal
- Entry: next candle breaks signal high
- Stop Loss: signal low
- Target: entry + 2 * (signal high - signal low)
"""

import pandas as pd
import pandas_ta as ta

# ------------------------
# CONFIG
# ------------------------
RSI_PERIOD = 14
RSI_LEVEL = 50

# Backtest CSV file (must have columns: date, open, high, low, close, volume)
CSV_FILE = "RELIANCE_5min.csv"

# ------------------------
# LOAD DATA
# ------------------------
df = pd.read_csv(CSV_FILE, parse_dates=["date"])
df = df.sort_values("date").reset_index(drop=True)

# Compute RSI
df["RSI"] = ta.rsi(df["close"], length=RSI_PERIOD)

# ------------------------
# BACKTEST LOGIC
# ------------------------
trades = []

state = {
    "signal_candle": None,
    "waiting_entry": False,
    "trade_taken": False
}

for i in range(1, len(df)):
    rsi_prev = df.loc[i - 1, "RSI"]
    rsi_curr = df.loc[i, "RSI"]

    # ----- PHASE 1: Signal detection -----
    if not state["waiting_entry"] and not state["trade_taken"]:
        if rsi_prev < RSI_LEVEL <= rsi_curr:
            # Signal candle is previous candle
            signal = df.loc[i - 1, ["high", "low", "close", "date"]].to_dict()
            state["signal_candle"] = signal
            state["waiting_entry"] = True

    # ----- PHASE 2: Entry -----
    elif state["waiting_entry"] and not state["trade_taken"]:
        sig = state["signal_candle"]
        candle = df.loc[i]

        # Check entry condition
        if candle["high"] > sig["high"]:
            entry_price = sig["high"]
            stop_loss = sig["low"]
            risk = sig["high"] - sig["low"]
            target = entry_price + (risk * 2)

            # Determine exit: look ahead until hit SL or target
            exit_price = None
            exit_time = None
            for j in range(i, len(df)):
                c = df.loc[j]
                if c["low"] <= stop_loss:
                    exit_price = stop_loss
                    exit_time = c["date"]
                    outcome = "SL"
                    break
                elif c["high"] >= target:
                    exit_price = target
                    exit_time = c["date"]
                    outcome = "Target"
                    break
            else:
                # End of data, exit at last close
                exit_price = df.loc[len(df) - 1, "close"]
                exit_time = df.loc[len(df) - 1, "date"]
                outcome = "Close"

            pnl = exit_price - entry_price

            trades.append({
                "Signal Time": sig["date"],
                "Entry Time": candle["date"],
                "Entry": entry_price,
                "SL": stop_loss,
                "Target": target,
                "Exit Time": exit_time,
                "Exit": exit_price,
                "Outcome": outcome,
                "PnL": pnl
            })

            # Reset state
            state["signal_candle"] = None
            state["waiting_entry"] = False
            state["trade_taken"] = False  # allow multiple signals

# ------------------------
# SAVE RESULTS
# ------------------------
trades_df = pd.DataFrame(trades)
trades_df.to_csv("RSI50_Backtest_Trades.csv", index=False)

# Summary
total_trades = len(trades_df)
winning_trades = trades_df[trades_df["PnL"] > 0].shape[0]
losing_trades = trades_df[trades_df["PnL"] <= 0].shape[0]
total_pnl = trades_df["PnL"].sum()
win_rate = (winning_trades / total_trades * 100) if total_trades else 0

print(f"Total Trades: {total_trades}")
print(f"Winning Trades: {winning_trades}")
print(f"Losing Trades: {losing_trades}")
print(f"Win Rate: {win_rate:.2f}%")
print(f"Total PnL: {total_pnl:.2f}")


"""
RSI-50 Crossover Intraday Strategy — Kite Connect
===================================================
Strategy Logic:
  - Timeframe  : 5-minute candles
  - Signal     : RSI crosses ABOVE 50
  - Entry      : Next candle breaks above the HIGH of the signal candle
  - Stop Loss  : LOW of the signal candle
  - Target     : Entry + (High_signal - Low_signal) * 2
  - Session    : 09:30 AM – 03:00 PM IST
"""

import time
import logging
from datetime import datetime, time as dtime

import pandas as pd
import pandas_ta as ta
from kiteconnect import KiteConnect

from utils.envs import envs
from utils.kite import get_kite

# ─────────────────────────────────────────────
# CONFIGURATION — loaded from .env
# ─────────────────────────────────────────────

SYMBOL       = envs.get("TRADE_SYMBOL") or "RELIANCE"   # Trading symbol
EXCHANGE     = envs.get("TRADE_EXCHANGE") or "NSE"
PRODUCT      = KiteConnect.PRODUCT_MIS                  # Intraday
ORDER_TYPE   = KiteConnect.ORDER_TYPE_LIMIT
QUANTITY     = int(envs.get("TRADE_QUANTITY") or "1")   # Shares per trade

RSI_PERIOD   = int(envs.get("RSI_PERIOD") or "14")
RSI_LEVEL    = 50

# Interval string understood by Kite (e.g. "5minute")
CANDLE_INTERVAL = envs.get("TRADE_INTERVAL") or "5minute"
LOOP_SLEEP      = 30               # Seconds between each loop tick

SESSION_START = dtime(9, 30)
SESSION_END   = dtime(15, 0)

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# KITE CONNECT SETUP
# ─────────────────────────────────────────────
kite = get_kite()
access_token = envs.get("KITE_ACCESS_TOKEN")
if access_token:
    kite.set_access_token(access_token)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def in_session() -> bool:
    """Return True if current time is within the allowed trading window."""
    now = datetime.now().time()
    return SESSION_START <= now <= SESSION_END


def get_instrument_token(symbol: str, exchange: str) -> int:
    """Fetch the instrument token for a given symbol."""
    instruments = kite.instruments(exchange)
    for inst in instruments:
        if inst["tradingsymbol"] == symbol:
            return inst["instrument_token"]
    raise ValueError(f"Instrument '{symbol}' not found on {exchange}.")


def fetch_candles(instrument_token: int, n: int = 50) -> pd.DataFrame:
    """
    Fetch the last `n` completed 5-minute candles.
    Returns a DataFrame with columns: date, open, high, low, close, volume.
    """
    from datetime import date, timedelta
    today = date.today()
    data  = kite.historical_data(
        instrument_token,
        from_date=today,
        to_date=today,
        interval=CANDLE_INTERVAL,
        continuous=False,
        oi=False,
    )
    df = pd.DataFrame(data)
    # Drop the still-forming (current) candle — keep only completed ones
    df = df.iloc[:-1].tail(n).reset_index(drop=True)
    return df


def compute_rsi(df: pd.DataFrame, period: int = RSI_PERIOD) -> pd.Series:
    """Compute RSI using pandas_ta."""
    rsi = ta.rsi(df["close"], length=period)
    return rsi


def rsi_crossed_50(rsi: pd.Series) -> bool:
    """
    Returns True if RSI crossed above 50 on the LATEST completed candle,
    i.e. previous RSI was below 50 and current RSI is above 50.
    """
    if len(rsi) < 2:
        return False
    prev = rsi.iloc[-2]
    curr = rsi.iloc[-1]
    return (prev is not None and curr is not None
            and prev < RSI_LEVEL <= curr)

def place_bracket_order(symbol: str, exchange: str,
                        entry_price: float,
                        stop_loss: float,
                        target: float,
                        quantity: int) -> str:
    """
    Place a MIS Limit order.
    Kite's bracket/cover order API varies by broker plan; here we place a
    plain limit entry and log SL/target for manual or OCO management.
    Replace with kite.place_order(variety=kite.VARIETY_BO, ...) if your
    plan supports Bracket Orders.
    """
    log.info(
        f"Placing BUY order | Entry={entry_price:.2f}  "
        f"SL={stop_loss:.2f}  Target={target:.2f}  Qty={quantity}"
    )
    order_id = kite.place_order(
        variety=KiteConnect.VARIETY_REGULAR,
        exchange=exchange,
        tradingsymbol=symbol,
        transaction_type=KiteConnect.TRANSACTION_TYPE_BUY,
        quantity=quantity,
        product=PRODUCT,
        order_type=ORDER_TYPE,
        price=round(entry_price, 2),
    )
    log.info(f"Order placed successfully. Order ID: {order_id}")
    return order_id


# ─────────────────────────────────────────────
# STRATEGY STATE
# ─────────────────────────────────────────────
from typing import Optional, Dict, Any


class StrategyState:
    def __init__(self) -> None:
        self.signal_candle: Optional[Dict[str, Any]] = None
        self.waiting_entry: bool = False
        self.trade_taken: bool = False  # one trade per signal

    def reset(self) -> None:
        self.signal_candle = None
        self.waiting_entry = False
        self.trade_taken = False


state = StrategyState()


# ─────────────────────────────────────────────
# MAIN LOOP
# ─────────────────────────────────────────────

def run():
    log.info("Strategy starting up …")
    instrument_token = get_instrument_token(SYMBOL, EXCHANGE)
    log.info(f"Instrument token for {SYMBOL}: {instrument_token}")

    last_processed_candle_time = None  # Track last candle we acted on

    while True:
        try:
            now = datetime.now()

            # ── Outside session: sleep and reset state at day end ──
            if not in_session():
                if now.time() > SESSION_END:
                    if state.waiting_entry or state.trade_taken:
                        log.info("Session over — resetting strategy state.")
                        state.reset()
                time.sleep(60)
                continue

            # ── Fetch latest candles ──
            df  = fetch_candles(instrument_token, n=RSI_PERIOD + 10)
            rsi = compute_rsi(df)

            latest_candle_time = df.iloc[-1]["date"]

            # ── Only process each new candle once ──
            if latest_candle_time == last_processed_candle_time:
                time.sleep(LOOP_SLEEP)
                continue

            last_processed_candle_time = latest_candle_time
            last_candle = df.iloc[-1]

            log.info(
                f"New candle @ {latest_candle_time} | "
                f"O={last_candle['open']:.2f}  H={last_candle['high']:.2f}  "
                f"L={last_candle['low']:.2f}  C={last_candle['close']:.2f}  "
                f"RSI={rsi.iloc[-1]:.2f}"
            )

            # ════════════════════════════════════════
            # PHASE 1 — Look for RSI crossover signal
            # ════════════════════════════════════════
            if not state.waiting_entry and not state.trade_taken:
                if rsi_crossed_50(rsi):
                    signal = {
                        "high"  : last_candle["high"],
                        "low"   : last_candle["low"],
                        "close" : last_candle["close"],
                        "time"  : latest_candle_time,
                    }
                    state.signal_candle = signal
                    state.waiting_entry = True
                    log.info(
                        f"✅ RSI crossed 50 — Signal candle recorded: "
                        f"H={signal['high']:.2f}  L={signal['low']:.2f}  "
                        f"C={signal['close']:.2f}"
                    )

            # ════════════════════════════════════════
            # PHASE 2 — Wait for next candle to break signal high
            # ════════════════════════════════════════
            elif state.waiting_entry and not state.trade_taken:
                sig = state.signal_candle

                if sig is None:
                    log.warning("State inconsistency: waiting_entry=True but signal_candle=None. Resetting.")
                    state.reset()
                    continue

                # Skip the signal candle itself
                if latest_candle_time == sig["time"]:
                    time.sleep(LOOP_SLEEP)
                    continue

                # Check if this candle's HIGH exceeds the signal candle's HIGH
                if last_candle["high"] > sig["high"]:
                    entry_price = sig["high"] + 0.05        # small buffer above signal high
                    stop_loss   = sig["low"]
                    risk        = sig["high"] - sig["low"]
                    target      = entry_price + (risk * 2)

                    log.info(
                        f"🚀 Entry triggered! Current H={last_candle['high']:.2f} "
                        f"> Signal H={sig['high']:.2f}"
                    )

                    place_bracket_order(
                        symbol      = SYMBOL,
                        exchange    = EXCHANGE,
                        entry_price = entry_price,
                        stop_loss   = stop_loss,
                        target      = target,
                        quantity    = QUANTITY,
                    )

                    state.trade_taken   = True
                    state.waiting_entry = False

                    log.info(
                        f"📊 Trade Summary → "
                        f"Entry: {entry_price:.2f} | "
                        f"SL: {stop_loss:.2f} | "
                        f"Target: {target:.2f} | "
                        f"Risk: {risk:.2f} | "
                        f"Reward: {risk * 2:.2f}"
                    )
                else:
                    log.info(
                        f"⏳ Waiting … Current H={last_candle['high']:.2f} "
                        f"has not crossed Signal H={sig['high']:.2f} yet."
                    )

            elif state.trade_taken:
                log.info("Trade already taken for this signal. Monitoring session …")

        except Exception as e:
            log.error(f"Error in main loop: {e}", exc_info=True)

        time.sleep(LOOP_SLEEP)


if __name__ == "__main__":
    run()
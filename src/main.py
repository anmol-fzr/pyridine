import sys
import webbrowser
from datetime import datetime, timedelta

import kiteconnect
import pandas as pd
import logging

from modules.engine.trade_executor import TradeExecutor
from modules.strategy.base import Candle
from modules.strategy.moving_average_strategy import MovingAverageStrategy
from utils.envs import envs
from utils.kite import get_kite

logging.basicConfig(
    filename='pyridine.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)
logger = logging.getLogger(" [MAIN] ")

INSTRUMENT_TOKEN = "408065"   # RELIANCE on NSE
TRADING_SYMBOL   = "RELIANCE"
CANDLE_INTERVAL  = "5minute"
LOOKBACK_DAYS    = 30          # days of historical candles to fetch
SHORT_MA         = 10
LONG_MA          = 20

req_token    = envs.get("KITE_REQUEST_TOKEN")
api_secret   = envs.get("KITE_API_SECRET")
access_token = envs.get("KITE_ACCESS_TOKEN")

kite = get_kite()


def authenticate():
    """Authenticate with Kite and handle token expiry / refresh."""
    try:
        if access_token:
            kite.set_access_token(access_token)

        profile = kite.profile()
        user = profile.get("user_name", "Unknown")
        logger.info(f" Authenticated as {user}")
        print(f"  ✓ Authenticated as {user}")
        return True

    except kiteconnect.exceptions.TokenException:
        print("  ✗ Access token invalid or expired.")
        logger.warning(" Access token invalid or expired")

        if req_token:
            print("    Generating new access token...")
            data = kite.generate_session(req_token, api_secret)
            kite.set_access_token(data["access_token"])

            print(f"    ✓ New access token: {data['access_token']}")
            print("    ⚠  Update KITE_ACCESS_TOKEN in your .env with the above token.")
            logger.info(" New access token generated")
            return True
        else:
            login_url = kite.login_url()
            print("    Opening Kite login to obtain request_token...")
            print(f"    URL: {login_url}")
            webbrowser.open(login_url)
            print("    After login, set KITE_REQUEST_TOKEN in .env and re-run.")
            return False

    except Exception as e:
        print(f"  ✗ Authentication error: {e}")
        logger.error(f" Authentication error: {e}")
        return False


def fetch_candles():
    """Fetch recent historical candle data from Kite."""
    to_date   = datetime.now()
    from_date = to_date - timedelta(days=LOOKBACK_DAYS)

    print(f"  Symbol:   {TRADING_SYMBOL} (token {INSTRUMENT_TOKEN})")
    print(f"  Interval: {CANDLE_INTERVAL}")
    print(f"  Range:    {from_date.strftime('%Y-%m-%d')} → {to_date.strftime('%Y-%m-%d')}")

    historical_data = kite.historical_data(
        instrument_token=INSTRUMENT_TOKEN,
        from_date=from_date.strftime("%Y-%m-%d %H:%M:%S"),
        to_date=to_date.strftime("%Y-%m-%d %H:%M:%S"),
        interval=CANDLE_INTERVAL
    )

    candles = [
        Candle(
            time=str(row["date"]),
            open=row["open"],
            high=row["high"],
            low=row["low"],
            close=row["close"],
            volume=row["volume"],
        )
        for row in historical_data
    ]

    print(f"  ✓ Fetched {len(candles)} candles")
    logger.info(f" Fetched {len(candles)} candles for {TRADING_SYMBOL}")
    return candles


def start():
    """Main entry point — authenticate, fetch data, and execute trades."""
    print("=" * 50)
    print("  PYRIDINE — Algorithmic Trading Engine")
    print("=" * 50)

    print("\n[1/3] Authenticating with Kite...")
    if not authenticate():
        sys.exit(1)

    print("\n[2/3] Fetching market data...")
    try:
        candles = fetch_candles()
    except Exception as e:
        print(f"  ✗ Failed to fetch candle data: {e}")
        logger.error(f" Failed to fetch candles: {e}")
        sys.exit(1)

    if not candles:
        print("  ✗ No candle data returned. Market may be closed.")
        sys.exit(1)

    print(f"\n[3/3] Running MovingAverage({SHORT_MA},{LONG_MA}) on {TRADING_SYMBOL}...")
    print(f"  ⚠  This will place REAL orders on your Kite account.")

    confirm = input("  Proceed? (y/n): ").strip().lower()
    if confirm != "y":
        print("  Aborted.")
        sys.exit(0)

    strategy = MovingAverageStrategy(short=SHORT_MA, long=LONG_MA)
    executor = TradeExecutor(strategy=strategy, kite=kite)

    executor.run(candles)
    results = executor.get_results()

    print(f"\n{'=' * 50}")
    print(f"  RESULTS — {len(results)} trade(s) executed")
    print(f"{'=' * 50}")

    if results:
        total_profit = sum(t.profit for t in results)

        df = pd.DataFrame([vars(t) for t in results])
        df.to_csv("trades_results.csv", index=False)

        print(df.to_string(index=False))
        print(f"\n  Total P&L: ₹{total_profit:.2f}")
        print(f"  Results saved to trades_results.csv")
        logger.info(f" {len(results)} trades — Total P&L: {total_profit:.2f}")
    else:
        print("  No trades were triggered by the strategy.")
        logger.info(" No trades triggered")

    print()


if __name__ == "__main__":
    start()

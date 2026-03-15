"""
Pyridine — Multi-Strategy Trading Engine

Usage:
    python src/main.py backtest     Run backtest for all strategies in config (default)
    python src/main.py live         Live-trade all strategies via WebSocket ticker
"""

import sys
import logging
import webbrowser
import kiteconnect

from utils.envs import envs
from utils.kite import get_kite

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pyridine")


# ── Authentication ──────────────────────────────────────────────────

def authenticate(kite: kiteconnect.KiteConnect) -> bool:
    """
    Authenticate the Kite session. Tries access_token first,
    falls back to generating a new session from request_token.
    """
    access_token = envs.get("KITE_ACCESS_TOKEN")
    api_secret = envs.get("KITE_API_SECRET")
    req_token = envs.get("KITE_REQUEST_TOKEN")

    try:
        if access_token:
            kite.set_access_token(access_token)

        profile = kite.profile()
        log.info("Authenticated as: %s (%s)", profile["user_name"], profile["user_id"])
        return True

    except kiteconnect.exceptions.TokenException:
        log.warning("Access token invalid or expired.")

        if req_token:
            log.info("Generating new access token from request_token...")
            data = kite.generate_session(req_token, api_secret)
            kite.set_access_token(data["access_token"])
            log.info("New access token: %s", data["access_token"])
            return True
        else:
            log.error("No request_token available. Opening Kite login...")
            webbrowser.open(kite.login_url())
            return False

    except Exception as e:
        log.error("Authentication failed: %s", e)
        return False


# ── Entry Point ─────────────────────────────────────────────────────


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "backtest"

    if mode not in ("backtest", "live"):
        print(__doc__)
        sys.exit(1)

    kite = get_kite()

    if not authenticate(kite):
        sys.exit(1)

    # Load all strategies from config
    from config.loader import load_strategies
    from strategies.engine import StrategyEngine

    strategies = load_strategies(kite)

    if not strategies:
        log.error("No strategies loaded. Check config/strategies.json.")
        sys.exit(1)

    engine = StrategyEngine(kite, strategies)

    if mode == "backtest":
        log.info("Running backtest for %d strategy instances...", len(strategies))
        engine.run_backtest()
    elif mode == "live":
        log.info("Starting live trading with %d strategy instances...", len(strategies))
        engine.run_live()


if __name__ == "__main__":
    main()

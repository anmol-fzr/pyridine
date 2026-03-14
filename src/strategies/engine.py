"""
Strategy Engine — orchestrates multiple strategies across multiple instruments.

Live mode:  Single KiteTicker WebSocket → dispatches ticks to all strategies.
Backtest:   Runs each strategy through historical candles → combined report.
"""

import datetime
import time
import logging
import threading
from collections import defaultdict

from kiteconnect import KiteTicker

from strategies.base import Strategy
from strategies.backtest import BacktestEngine, generate_report, generate_combined_report
from utils.action_logger import ActionLogger

log = logging.getLogger(__name__)


class StrategyEngine:
    """
    Manages N strategy instances across M instruments.

    - In live mode, creates one WebSocket and dispatches ticks.
    - In backtest mode, fetches candles per instrument and runs each strategy.
    """

    def __init__(self, kite, strategies: list[Strategy]):
        self.kite = kite
        self.strategies = strategies

        # Build dispatch map: instrument_token → [strategy, ...]
        self._dispatch: dict[int, list[Strategy]] = defaultdict(list)
        for s in strategies:
            self._dispatch[s.instrument_token].append(s)

        # Build ActionLogger dict for live mode (each saves to reports/<strategy_label>)
        self._action_loggers: dict[str, ActionLogger] = {}
        for s in strategies:
            safe_label = s.label.replace(':', '_')
            out_dir = f"reports/{safe_label}"
            self._action_loggers[s.label] = ActionLogger(output_dir=out_dir)

        # All unique tokens to subscribe
        self._tokens = list(self._dispatch.keys())

        log.info(
            "Engine initialized: %d strategies across %d instruments",
            len(strategies), len(self._tokens),
        )

    # ── Live Mode ───────────────────────────────────────────────────

    def run_live(self, candle_refresh_seconds: int = 300):
        """
        Start the WebSocket ticker and dispatch ticks to all strategies.

        Args:
            candle_refresh_seconds: How often to refresh candles (default 5min).
        """
        api_key = self.kite.api_key
        access_token = self.kite.access_token

        kws = KiteTicker(api_key, access_token)

        def on_ticks(ws, ticks):
            for tick in ticks:
                token = tick["instrument_token"]
                last_price = tick["last_price"]

                for strategy in self._dispatch.get(token, []):
                    if strategy.on_tick(last_price):
                        order_id = strategy.execute_buy(last_price)
                        if order_id is not None:
                            logger = self._action_loggers.get(strategy.label)
                            if logger:
                                logger.log_action(
                                    mode="live",
                                    strategy_label=strategy.label,
                                    symbol=strategy.tradingsymbol,
                                    action="BUY",
                                    trigger_price=last_price,
                                    candle=strategy.latest_candle
                                )

        def on_connect(ws, response):
            log.info("WebSocket connected. Subscribing to %d tokens.", len(self._tokens))
            ws.subscribe(self._tokens)
            ws.set_mode(ws.MODE_FULL, self._tokens)

        def on_close(ws, code, reason):
            log.warning("WebSocket closed: code=%s reason=%s", code, reason)

        def on_error(ws, code, reason):
            log.error("WebSocket error: code=%s reason=%s", code, reason)

        def on_reconnect(ws, attempts_count):
            log.info("WebSocket reconnecting... attempt %d", attempts_count)

        def on_noreconnect(ws):
            log.error("WebSocket could not reconnect. Giving up.")

        # Background candle refresh for all strategies
        def candle_refresh_loop():
            while True:
                time.sleep(candle_refresh_seconds)
                log.info("Refreshing candles for all strategies...")
                for strategy in self.strategies:
                    try:
                        strategy.refresh_candles()
                    except Exception as e:
                        log.error("[%s] Candle refresh failed: %s", strategy.label, e)

        refresh_thread = threading.Thread(target=candle_refresh_loop, daemon=True)
        refresh_thread.start()

        kws.on_ticks = on_ticks
        kws.on_connect = on_connect
        kws.on_close = on_close
        kws.on_error = on_error
        kws.on_reconnect = on_reconnect
        kws.on_noreconnect = on_noreconnect

        log.info("Starting WebSocket ticker (blocking)...")
        kws.connect(threaded=False)

    # ── Backtest Mode ───────────────────────────────────────────────

    def run_backtest(
        self,
        days: int = 60,
        capital: float = 100_000.0,
        output_dir: str = "reports",
    ):
        """
        Run backtest for every strategy instance and generate reports.

        Fetches historical candles per instrument, runs each strategy's
        backtest_check, then generates per-strategy and combined reports.
        """
        now = datetime.datetime.now()
        from_date = now - datetime.timedelta(days=days)

        all_results: dict[str, "BacktestResult"] = {}

        # Fetch candles per unique (token, interval) to avoid duplicates
        candle_cache: dict[tuple[int, str], list[dict]] = {}

        for strategy in self.strategies:
            interval = strategy.params.get("interval", "5minute")
            cache_key = (strategy.instrument_token, interval)

            if cache_key not in candle_cache:
                log.info(
                    "Fetching %s candles for %s:%s (token=%d)...",
                    interval, strategy.exchange, strategy.tradingsymbol,
                    strategy.instrument_token,
                )
                candles = self.kite.historical_data(
                    instrument_token=strategy.instrument_token,
                    from_date=from_date,
                    to_date=now,
                    interval=interval,
                )
                candle_cache[cache_key] = candles
                log.info("Fetched %d candles.", len(candles))

            candles = candle_cache[cache_key]

            if not candles:
                log.error("[%s] No candle data — skipping.", strategy.label)
                continue

            # Run backtest for this strategy
            rsi_period = int(strategy.params.get("rsi_period", 14))
            engine = BacktestEngine(
                candles=candles,
                rsi_period=rsi_period,
                quantity=strategy.quantity,
                capital=capital,
                strategy=strategy,
            )

            log.info("[%s] Running backtest...", strategy.label)
            result = engine.run()
            all_results[strategy.label] = result

            # Per-strategy report
            strategy_dir = f"{output_dir}/{strategy.label.replace(':', '_')}"
            generate_report(result, output_dir=strategy_dir, title=strategy.label)

        # Combined comparison report
        if len(all_results) > 1:
            generate_combined_report(all_results, output_dir=output_dir)

        return all_results

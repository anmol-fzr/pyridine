"""
Config loader — reads strategies.json and instantiates Strategy objects.
"""

import json
import os
import logging

from kiteconnect import KiteConnect

from strategies.base import Strategy

log = logging.getLogger(__name__)

# Registry: strategy type string → Strategy subclass
_STRATEGY_REGISTRY: dict[str, type[Strategy]] = {}


def register_strategy(type_name: str):
    """Decorator to register a strategy class under a type name."""
    def decorator(cls: type[Strategy]):
        _STRATEGY_REGISTRY[type_name] = cls
        return cls
    return decorator


def get_registered_strategies() -> dict[str, type[Strategy]]:
    """Return a copy of the strategy registry."""
    return dict(_STRATEGY_REGISTRY)


def _resolve_instrument_token(kite, exchange: str, symbol: str) -> int | None:
    """Look up instrument_token via kite.instruments()."""
    instruments = kite.instruments(exchange)
    for inst in instruments:
        if inst["tradingsymbol"] == symbol:
            return inst["instrument_token"]
    return None


# Cache for instrument lists to avoid repeated API calls
_instrument_cache: dict[str, list[dict]] = {}


def _resolve_instrument_token_cached(kite, exchange: str, symbol: str) -> int | None:
    """Look up instrument_token with caching per exchange."""
    if exchange not in _instrument_cache:
        log.info("Fetching instrument list for exchange: %s", exchange)
        _instrument_cache[exchange] = kite.instruments(exchange)

    for inst in _instrument_cache[exchange]:
        if inst["tradingsymbol"] == symbol:
            return inst["instrument_token"]
    return None


def load_strategies(
    kite: KiteConnect,
    config_path: str | None = None,
) -> list[Strategy]:
    """
    Load strategies.json and create Strategy instances.

    Args:
        kite: Authenticated KiteConnect instance.
        config_path: Path to strategies.json. Defaults to src/config/strategies.json.

    Returns:
        List of instantiated Strategy objects.
    """
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(__file__), "strategies.json"
        )

    with open(config_path) as f:
        config = json.load(f)

    # Ensure strategy subclasses are imported (triggers @register_strategy)
    _ensure_strategies_imported()

    strategies: list[Strategy] = []

    for entry in config.get("strategies", []):
        strategy_type = entry["type"]
        params = entry.get("params", {})

        cls = _STRATEGY_REGISTRY.get(strategy_type)
        if cls is None:
            log.error(
                "Unknown strategy type '%s'. Registered: %s",
                strategy_type,
                list(_STRATEGY_REGISTRY.keys()),
            )
            continue

        for instrument in entry.get("instruments", []):
            symbol = instrument["symbol"]
            exchange = instrument["exchange"]
            quantity = instrument.get("quantity", 1)

            token = _resolve_instrument_token_cached(kite, exchange, symbol)
            if token is None:
                log.error("Could not find token for %s:%s — skipping.", exchange, symbol)
                continue

            strategy = cls(
                kite=kite,
                instrument_token=token,
                tradingsymbol=symbol,
                exchange=exchange,
                quantity=quantity,
                **params,
            )

            log.info("Loaded strategy: %s", strategy.label)
            strategies.append(strategy)

    log.info("Total strategy instances loaded: %d", len(strategies))
    return strategies


def _ensure_strategies_imported():
    """Import all strategy modules so @register_strategy decorators run."""
    # Add imports here as new strategies are created.
    import strategies.rsi_breakout  # noqa: F401

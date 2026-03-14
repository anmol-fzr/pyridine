"""
RSI (Relative Strength Index) indicator using Wilder's smoothing.
"""


def compute_rsi(closes: list[float], period: int = 14) -> float:
    """
    Compute RSI using Wilder's smoothing method.

    Args:
        closes: List of closing prices. Needs at least (period + 1) values.
        period: Look-back period (default 14).

    Returns:
        RSI value between 0 and 100.

    Raises:
        ValueError: If not enough data points.
    """
    if len(closes) < period + 1:
        raise ValueError(
            f"Need at least {period + 1} closing prices, got {len(closes)}"
        )

    # Calculate price changes
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    # Seed: simple average of first `period` gains and losses
    gains = [d if d > 0 else 0.0 for d in deltas[:period]]
    losses = [-d if d < 0 else 0.0 for d in deltas[:period]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    # Wilder's smoothing for the remaining deltas
    for d in deltas[period:]:
        gain = d if d > 0 else 0.0
        loss = -d if d < 0 else 0.0

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def compute_rsi_series(closes: list[float], period: int = 14) -> list[float]:
    """
    Compute RSI for every point where enough data exists.

    Returns a list of RSI values. The first RSI corresponds to
    closes[period], the last to closes[-1].
    Length of result = len(closes) - period.
    """
    if len(closes) < period + 1:
        raise ValueError(
            f"Need at least {period + 1} closing prices, got {len(closes)}"
        )

    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]

    # Seed
    gains = [d if d > 0 else 0.0 for d in deltas[:period]]
    losses = [-d if d < 0 else 0.0 for d in deltas[:period]]

    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period

    rsi_values = []

    # RSI at index = period (first valid point)
    if avg_loss == 0:
        rsi_values.append(100.0)
    else:
        rs = avg_gain / avg_loss
        rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    # Wilder's smoothing for the rest
    for d in deltas[period:]:
        gain = d if d > 0 else 0.0
        loss = -d if d < 0 else 0.0

        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

        if avg_loss == 0:
            rsi_values.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi_values.append(100.0 - (100.0 / (1.0 + rs)))

    return rsi_values

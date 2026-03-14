"""Tests for utils.indicators — RSI computation."""

import pytest
from utils.indicators import compute_rsi, compute_rsi_series


class TestComputeRSI:
    """Tests for the single-value RSI function."""

    def test_insufficient_data_raises(self):
        """Need at least period+1 data points."""
        with pytest.raises(ValueError, match="Need at least 15"):
            compute_rsi([100.0] * 10, period=14)

    def test_all_gains_returns_100(self):
        """If price only goes up, RSI should be 100."""
        # 16 points = 15 deltas, all positive
        closes = [float(i) for i in range(100, 116)]
        rsi = compute_rsi(closes, period=14)
        assert rsi == 100.0

    def test_all_losses_returns_0(self):
        """If price only goes down, RSI should be 0."""
        closes = [float(200 - i) for i in range(16)]
        rsi = compute_rsi(closes, period=14)
        assert rsi == 0.0

    def test_known_value(self):
        """
        Hand-verified RSI calculation.
        Prices: 44, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10,
                45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28
        Expected RSI(14) ≈ 70.46 (classic Wilder example values, approximately).
        """
        closes = [
            44.0, 44.34, 44.09, 43.61, 44.33, 44.83, 45.10,
            45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28,
        ]
        rsi = compute_rsi(closes, period=14)
        # RSI should be between 60 and 80 for this dataset
        assert 60 < rsi < 80, f"RSI={rsi} outside expected range"

    def test_flat_prices(self):
        """If price doesn't change, avg_loss=0 → RSI=100 (no losses)."""
        closes = [50.0] * 16
        rsi = compute_rsi(closes, period=14)
        # All deltas are 0 → avg_gain=0, avg_loss=0 → division guard → 100
        assert rsi == 100.0

    def test_rsi_bounds(self):
        """RSI must always be between 0 and 100."""
        import random
        random.seed(42)
        closes = [100 + random.uniform(-5, 5) for _ in range(50)]
        rsi = compute_rsi(closes, period=14)
        assert 0 <= rsi <= 100


class TestComputeRSISeries:
    """Tests for the RSI series function."""

    def test_series_length(self):
        """Result length = len(closes) - period."""
        closes = [float(i) for i in range(30)]
        series = compute_rsi_series(closes, period=14)
        assert len(series) == 30 - 14

    def test_series_last_matches_single(self):
        """Last value in series should match compute_rsi on the full array."""
        import random
        random.seed(99)
        closes = [100 + random.uniform(-3, 3) for _ in range(50)]
        series = compute_rsi_series(closes, period=14)
        single = compute_rsi(closes, period=14)
        assert abs(series[-1] - single) < 0.001

    def test_all_values_in_bounds(self):
        """Every RSI in the series must be 0–100."""
        import random
        random.seed(7)
        closes = [100 + random.uniform(-10, 10) for _ in range(100)]
        series = compute_rsi_series(closes, period=14)
        for val in series:
            assert 0 <= val <= 100, f"RSI={val} out of bounds"

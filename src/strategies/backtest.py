"""
Backtesting engine for trading strategies.

Replays historical candles through a strategy's backtest_check method,
tracks trades/equity/drawdown, and generates matplotlib visualizations.
Supports both single-strategy and multi-strategy comparison reports.
"""

import datetime
import logging
import os
from dataclasses import dataclass, field

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from utils.action_logger import ActionLogger

log = logging.getLogger(__name__)


# ── Data Classes ────────────────────────────────────────────────────


@dataclass
class Trade:
    """A single simulated trade."""
    entry_index: int
    entry_time: datetime.datetime
    entry_price: float
    exit_price: float
    pnl: float = 0.0
    is_win: bool = False

    def __post_init__(self):
        self.pnl = self.exit_price - self.entry_price
        self.is_win = self.pnl > 0


@dataclass
class BacktestResult:
    """Aggregated results from a backtest run."""
    trades: list[Trade] = field(default_factory=list)
    equity_curve: list[float] = field(default_factory=list)
    timestamps: list[datetime.datetime] = field(default_factory=list)
    initial_capital: float = 100_000.0

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.is_win)

    @property
    def losses(self) -> int:
        return self.total_trades - self.wins

    @property
    def win_rate(self) -> float:
        return (self.wins / self.total_trades * 100) if self.total_trades else 0.0

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades)

    @property
    def avg_win(self) -> float:
        wins = [t.pnl for t in self.trades if t.is_win]
        return sum(wins) / len(wins) if wins else 0.0

    @property
    def avg_loss(self) -> float:
        losses = [t.pnl for t in self.trades if not t.is_win]
        return sum(losses) / len(losses) if losses else 0.0

    @property
    def max_drawdown(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd = 0.0
        for val in self.equity_curve:
            if val > peak:
                peak = val
            dd = peak - val
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def max_drawdown_pct(self) -> float:
        if not self.equity_curve:
            return 0.0
        peak = self.equity_curve[0]
        max_dd_pct = 0.0
        for val in self.equity_curve:
            if val > peak:
                peak = val
            dd_pct = ((peak - val) / peak) * 100 if peak else 0.0
            if dd_pct > max_dd_pct:
                max_dd_pct = dd_pct
        return max_dd_pct


# ── Backtest Engine ─────────────────────────────────────────────────


class BacktestEngine:
    """
    Replays historical candles through a strategy's backtest_check method.

    For each candle, if backtest_check fires, the entry is at the current
    candle's close and exit is at the next candle's close.
    """

    def __init__(
        self,
        candles: list[dict],
        rsi_period: int = 14,
        quantity: int = 1,
        capital: float = 100_000.0,
        strategy=None,
        output_dir: str = "reports/backtest",
    ):
        self.candles = candles
        self.rsi_period = rsi_period
        self.quantity = quantity
        self.initial_capital = capital
        self.strategy = strategy
        self.output_dir = output_dir
        
        # Instantiate localized action logger
        out_dir = self.output_dir
        if strategy:
            safe_label = strategy.label.replace(':', '_')
            out_dir = f"{self.output_dir}/{safe_label}"
        self.action_logger = ActionLogger(output_dir=out_dir)

    def run(self) -> BacktestResult:
        """Execute the backtest and return results."""
        if len(self.candles) < self.rsi_period + 2:
            log.warning(
                "Not enough candles (%d) for RSI(%d). Need at least %d.",
                len(self.candles), self.rsi_period, self.rsi_period + 2,
            )
            return BacktestResult(initial_capital=self.initial_capital)

        result = BacktestResult(initial_capital=self.initial_capital)
        capital = self.initial_capital

        for i in range(self.rsi_period + 1, len(self.candles) - 1):
            candle = self.candles[i]

            # Track equity
            result.equity_curve.append(capital)
            result.timestamps.append(candle["date"])

            # Use strategy's backtest_check if available, else fallback to
            # RSI + prev-high logic
            signal = False
            if self.strategy is not None:
                signal = self.strategy.backtest_check(self.candles, i)
            else:
                signal = self._default_check(i)

            if signal:
                next_candle = self.candles[i + 1]
                entry_price = candle["close"]
                exit_price = next_candle["close"]

                strategy_label = self.strategy.label if self.strategy else "RSI Breakout (Default)"
                symbol = self.strategy.tradingsymbol if self.strategy else "UNKNOWN"

                self.action_logger.log_action(
                    mode="backtest",
                    strategy_label=strategy_label,
                    symbol=symbol,
                    action="BUY",
                    trigger_price=entry_price,
                    candle=candle
                )

                trade = Trade(
                    entry_index=i,
                    entry_time=candle["date"],
                    entry_price=entry_price,
                    exit_price=exit_price,
                )

                capital += trade.pnl * self.quantity
                result.trades.append(trade)

                log.debug(
                    "Trade #%d @ %s: entry=%.2f exit=%.2f pnl=%.2f",
                    len(result.trades), candle["date"],
                    entry_price, exit_price, trade.pnl * self.quantity,
                )

        # Final equity point
        if result.timestamps:
            result.equity_curve.append(capital)
            result.timestamps.append(self.candles[-1]["date"])

        return result

    def _default_check(self, index: int) -> bool:
        """Fallback RSI breakout check when no strategy object is provided."""
        from utils.indicators import compute_rsi

        if index < self.rsi_period + 1 or index < 1:
            return False

        closes = [c["close"] for c in self.candles[: index + 1]]
        rsi = compute_rsi(closes, self.rsi_period)
        prev_high = self.candles[index - 1]["high"]
        current_close = self.candles[index]["close"]

        return rsi > 50 and current_close > prev_high


# ── Chart Styling ───────────────────────────────────────────────────

DARK_BG = "#1a1a2e"
PANEL_BG = "#16213e"
GRID_COLOR = "#2a2a4a"
WIN_COLOR = "#00ff88"
LOSS_COLOR = "#ff4444"
LINE_COLOR = "#00d2ff"


def _style_axis(ax):
    """Apply dark theme to an axis."""
    ax.set_facecolor(PANEL_BG)
    ax.tick_params(colors="#888")
    ax.grid(color=GRID_COLOR, alpha=0.5)


# ── Single-Strategy Report ──────────────────────────────────────────


def generate_report(
    result: BacktestResult,
    output_dir: str = "reports",
    title: str = "RSI Breakout",
):
    """Generate charts and summary for a single strategy."""
    os.makedirs(output_dir, exist_ok=True)

    # ── Summary Stats ──
    summary_lines = [
        "=" * 55,
        f"  {title} — BACKTEST REPORT",
        "=" * 55,
        f"  Initial Capital    : ₹{result.initial_capital:,.2f}",
        f"  Final Capital      : ₹{result.equity_curve[-1]:,.2f}" if result.equity_curve else "  Final Capital      : N/A",
        f"  Net P&L            : ₹{result.total_pnl:,.2f}",
        f"  Total Trades       : {result.total_trades}",
        f"  Wins / Losses      : {result.wins} / {result.losses}",
        f"  Win Rate           : {result.win_rate:.1f}%",
        f"  Avg Win            : ₹{result.avg_win:,.2f}",
        f"  Avg Loss           : ₹{result.avg_loss:,.2f}",
        f"  Max Drawdown       : ₹{result.max_drawdown:,.2f} ({result.max_drawdown_pct:.2f}%)",
        "=" * 55,
    ]
    summary_text = "\n".join(summary_lines)
    print(summary_text)

    with open(os.path.join(output_dir, "summary.txt"), "w") as f:
        f.write(summary_text + "\n")

    if not result.trades:
        print("\n  No trades — charts not generated.")
        return

    # ── Equity Curve ──
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor(DARK_BG)
    _style_axis(ax)

    ax.plot(result.timestamps, result.equity_curve, color=LINE_COLOR, linewidth=1.5, label="Equity")

    # Trade markers
    for t in result.trades:
        color = WIN_COLOR if t.is_win else LOSS_COLOR
        marker = "^" if t.is_win else "v"
        try:
            idx = result.timestamps.index(t.entry_time)
            eq = result.equity_curve[idx]
        except ValueError:
            eq = result.initial_capital
        ax.scatter(t.entry_time, eq, color=color, marker=marker, s=50, zorder=5)

    ax.set_title(f"{title} — Equity Curve", color="white", fontsize=15, fontweight="bold", pad=12)
    ax.set_xlabel("Time", color="#aaa", fontsize=11)
    ax.set_ylabel("Capital (₹)", color="#aaa", fontsize=11)
    ax.legend(facecolor=PANEL_BG, edgecolor="#333", labelcolor="white", fontsize=10)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d %H:%M"))
    fig.autofmt_xdate()
    fig.savefig(os.path.join(output_dir, "equity_curve.png"), dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)

    # ── PnL per Trade ──
    fig, ax = plt.subplots(figsize=(14, 6))
    fig.patch.set_facecolor(DARK_BG)
    _style_axis(ax)

    pnls = [t.pnl for t in result.trades]
    colors = [WIN_COLOR if p > 0 else LOSS_COLOR for p in pnls]
    ax.bar(range(1, len(pnls) + 1), pnls, color=colors, edgecolor="#333", width=0.7)
    ax.axhline(y=0, color="#666", linewidth=0.8, linestyle="--")

    ax.set_title(f"{title} — P&L per Trade", color="white", fontsize=15, fontweight="bold", pad=12)
    ax.set_xlabel("Trade #", color="#aaa", fontsize=11)
    ax.set_ylabel("P&L (₹)", color="#aaa", fontsize=11)
    fig.savefig(os.path.join(output_dir, "pnl_per_trade.png"), dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)

    # ── Win/Loss Pie ──
    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_facecolor(DARK_BG)

    ax.pie(
        [result.wins, result.losses],
        labels=[f"Wins ({result.wins})", f"Losses ({result.losses})"],
        colors=[WIN_COLOR, LOSS_COLOR],
        autopct="%1.1f%%",
        startangle=90,
        textprops={"color": "white", "fontsize": 12},
    )
    ax.set_title(f"{title} — Win/Loss", color="white", fontsize=15, fontweight="bold", pad=12)
    fig.savefig(os.path.join(output_dir, "win_loss.png"), dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)

    print(f"\n  📊 Charts saved to {output_dir}/")


# ── Multi-Strategy Combined Report ──────────────────────────────────


def generate_combined_report(
    results: dict[str, BacktestResult],
    output_dir: str = "reports",
):
    """
    Generate a side-by-side comparison of multiple strategy backtests.

    Args:
        results: Mapping of strategy_label → BacktestResult.
        output_dir: Directory to save charts.
    """
    os.makedirs(output_dir, exist_ok=True)

    labels = list(results.keys())
    result_list = [results[l] for l in labels]

    # ── Overlaid Equity Curves ──
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor(DARK_BG)
    _style_axis(ax)

    palette = ["#00d2ff", "#ff6b6b", "#ffd93d", "#6bff6b", "#c084fc", "#ff9f43"]
    for i, (label, res) in enumerate(zip(labels, result_list)):
        if res.timestamps:
            color = palette[i % len(palette)]
            ax.plot(res.timestamps, res.equity_curve, color=color, linewidth=1.5, label=label)

    ax.set_title("Strategy Comparison — Equity Curves", color="white", fontsize=16, fontweight="bold", pad=15)
    ax.set_xlabel("Time", color="#aaa", fontsize=11)
    ax.set_ylabel("Capital (₹)", color="#aaa", fontsize=11)
    ax.legend(facecolor=PANEL_BG, edgecolor="#333", labelcolor="white", fontsize=10, loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
    fig.autofmt_xdate()
    fig.savefig(os.path.join(output_dir, "comparison_equity.png"), dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)

    # ── Win Rate Comparison ──
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor(DARK_BG)
    _style_axis(ax)

    win_rates = [r.win_rate for r in result_list]
    bar_colors = [palette[i % len(palette)] for i in range(len(labels))]
    bars = ax.bar(labels, win_rates, color=bar_colors, edgecolor="#333", width=0.5)

    for bar, wr in zip(bars, win_rates):
        ax.text(
            bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
            f"{wr:.1f}%", ha="center", color="white", fontsize=11, fontweight="bold",
        )

    ax.set_title("Win Rate Comparison", color="white", fontsize=16, fontweight="bold", pad=15)
    ax.set_ylabel("Win Rate (%)", color="#aaa", fontsize=11)
    ax.set_ylim(0, 100)
    plt.xticks(rotation=20, ha="right")
    fig.savefig(os.path.join(output_dir, "comparison_winrate.png"), dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)

    # ── PnL Comparison ──
    fig, ax = plt.subplots(figsize=(10, 6))
    fig.patch.set_facecolor(DARK_BG)
    _style_axis(ax)

    total_pnls = [r.total_pnl for r in result_list]
    pnl_colors = [WIN_COLOR if p > 0 else LOSS_COLOR for p in total_pnls]
    bars = ax.bar(labels, total_pnls, color=pnl_colors, edgecolor="#333", width=0.5)

    for bar, pnl in zip(bars, total_pnls):
        y_pos = bar.get_height() + (1 if pnl >= 0 else -3)
        ax.text(
            bar.get_x() + bar.get_width() / 2, y_pos,
            f"₹{pnl:,.1f}", ha="center", color="white", fontsize=11, fontweight="bold",
        )

    ax.axhline(y=0, color="#666", linewidth=0.8, linestyle="--")
    ax.set_title("Total P&L Comparison", color="white", fontsize=16, fontweight="bold", pad=15)
    ax.set_ylabel("P&L (₹)", color="#aaa", fontsize=11)
    plt.xticks(rotation=20, ha="right")
    fig.savefig(os.path.join(output_dir, "comparison_pnl.png"), dpi=150, bbox_inches="tight", facecolor=DARK_BG)
    plt.close(fig)

    # ── Summary Table ──
    summary_lines = [
        "=" * 70,
        "  MULTI-STRATEGY BACKTEST COMPARISON",
        "=" * 70,
        f"  {'Strategy':<30} {'Trades':>7} {'Win%':>7} {'PnL':>12} {'MaxDD':>10}",
        "-" * 70,
    ]
    for label, res in zip(labels, result_list):
        summary_lines.append(
            f"  {label:<30} {res.total_trades:>7} {res.win_rate:>6.1f}% "
            f"₹{res.total_pnl:>10,.1f} ₹{res.max_drawdown:>8,.1f}"
        )
    summary_lines.append("=" * 70)

    summary_text = "\n".join(summary_lines)
    print("\n" + summary_text)

    with open(os.path.join(output_dir, "comparison_summary.txt"), "w") as f:
        f.write(summary_text + "\n")

    print(f"\n  📊 Combined charts saved to {output_dir}/")

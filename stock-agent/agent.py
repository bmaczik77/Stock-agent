#!/usr/bin/env python3
"""
Stock Analysis Agent - Main entry point.

Combines fundamental and technical analysis to produce comprehensive
stock reports with buy/hold/sell recommendations.
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from fundamental_analyzer import FundamentalAnalyzer
from sector_comparison import SectorComparison

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONFIG_PATH = Path(__file__).parent / "config.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    """Load analysis configuration from config.json."""
    with open(CONFIG_PATH) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Technical Analysis helpers
# ---------------------------------------------------------------------------


def calculate_sma(prices: pd.Series, window: int) -> pd.Series:
    """Simple Moving Average."""
    return prices.rolling(window=window).mean()


def calculate_ema(prices: pd.Series, span: int) -> pd.Series:
    """Exponential Moving Average."""
    return prices.ewm(span=span, adjust=False).mean()


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calculate_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict:
    """MACD line, signal line, and histogram."""
    ema_fast = calculate_ema(prices, fast)
    ema_slow = calculate_ema(prices, slow)
    macd_line = ema_fast - ema_slow
    signal_line = calculate_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
    }


def calculate_bollinger_bands(
    prices: pd.Series, window: int = 20, num_std: float = 2.0
) -> dict:
    """Bollinger Bands (upper, middle, lower)."""
    middle = calculate_sma(prices, window)
    std = prices.rolling(window=window).std()
    return {
        "upper": middle + num_std * std,
        "middle": middle,
        "lower": middle - num_std * std,
    }


def calculate_atr(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Average True Range."""
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


def calculate_obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """On-Balance Volume."""
    direction = np.sign(close.diff())
    return (volume * direction).cumsum()


# ---------------------------------------------------------------------------
# Technical Analysis report
# ---------------------------------------------------------------------------


class TechnicalAnalyzer:
    """Run all technical indicators and derive a signal."""

    def __init__(self, config: dict):
        self.cfg = config.get("technical_analysis", {})

    def analyze(self, ticker: str, period: str = "1y") -> dict:
        """Download price data and compute indicators."""
        logger.info("Fetching price data for %s (period=%s)", ticker, period)
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)

        if hist.empty:
            return {"error": f"No price data found for {ticker}"}

        close = hist["Close"]
        high = hist["High"]
        low = hist["Low"]
        volume = hist["Volume"]

        # Moving averages
        sma_periods = self.cfg.get("sma_periods", [20, 50, 200])
        smas = {f"SMA_{p}": calculate_sma(close, p).iloc[-1] for p in sma_periods}

        ema_periods = self.cfg.get("ema_periods", [12, 26])
        emas = {f"EMA_{p}": calculate_ema(close, p).iloc[-1] for p in ema_periods}

        # RSI
        rsi_period = self.cfg.get("rsi_period", 14)
        rsi = calculate_rsi(close, rsi_period)

        # MACD
        macd = calculate_macd(close)

        # Bollinger Bands
        bb = calculate_bollinger_bands(close)

        # ATR
        atr = calculate_atr(high, low, close)

        # OBV
        obv = calculate_obv(close, volume)

        current_price = close.iloc[-1]

        # --- Derive signal scores ---
        score = 0
        reasons = []

        # Trend: price vs SMA-50 & SMA-200
        if "SMA_50" in smas and "SMA_200" in smas:
            if smas["SMA_50"] > smas["SMA_200"]:
                score += 1
                reasons.append("Golden cross (SMA50 > SMA200)")
            else:
                score -= 1
                reasons.append("Death cross (SMA50 < SMA200)")

        # RSI
        latest_rsi = rsi.iloc[-1]
        if latest_rsi < 30:
            score += 1
            reasons.append(f"RSI oversold ({latest_rsi:.1f})")
        elif latest_rsi > 70:
            score -= 1
            reasons.append(f"RSI overbought ({latest_rsi:.1f})")
        else:
            reasons.append(f"RSI neutral ({latest_rsi:.1f})")

        # MACD
        if macd["histogram"].iloc[-1] > 0:
            score += 1
            reasons.append("MACD histogram positive")
        else:
            score -= 1
            reasons.append("MACD histogram negative")

        # Bollinger Bands
        if current_price < bb["lower"].iloc[-1]:
            score += 1
            reasons.append("Price below lower Bollinger Band")
        elif current_price > bb["upper"].iloc[-1]:
            score -= 1
            reasons.append("Price above upper Bollinger Band")

        # Map score to signal
        if score >= 2:
            signal = "BUY"
        elif score <= -2:
            signal = "SELL"
        else:
            signal = "HOLD"

        return {
            "ticker": ticker,
            "current_price": round(current_price, 2),
            "moving_averages": {k: round(v, 2) for k, v in {**smas, **emas}.items()},
            "rsi": round(latest_rsi, 2),
            "macd": {
                "line": round(macd["macd_line"].iloc[-1], 4),
                "signal": round(macd["signal_line"].iloc[-1], 4),
                "histogram": round(macd["histogram"].iloc[-1], 4),
            },
            "bollinger_bands": {
                "upper": round(bb["upper"].iloc[-1], 2),
                "middle": round(bb["middle"].iloc[-1], 2),
                "lower": round(bb["lower"].iloc[-1], 2),
            },
            "atr": round(atr.iloc[-1], 2),
            "obv": int(obv.iloc[-1]),
            "technical_score": score,
            "technical_signal": signal,
            "reasons": reasons,
        }


# ---------------------------------------------------------------------------
# Combined report
# ---------------------------------------------------------------------------


def generate_report(ticker: str, config: dict) -> dict:
    """Produce a unified analysis combining fundamental + technical data."""
    report: dict = {
        "ticker": ticker,
        "generated_at": datetime.now().isoformat(),
    }

    # Technical
    tech = TechnicalAnalyzer(config)
    report["technical"] = tech.analyze(
        ticker, period=config.get("default_period", "1y")
    )

    # Fundamental
    fa = FundamentalAnalyzer(config)
    report["fundamental"] = fa.analyze(ticker)

    # Sector comparison
    sc = SectorComparison(config)
    report["sector_comparison"] = sc.compare(ticker)

    # --- Overall recommendation ---
    tech_signal = report["technical"].get("technical_signal", "HOLD")
    fund_signal = report["fundamental"].get("fundamental_signal", "HOLD")

    signal_map = {"BUY": 1, "HOLD": 0, "SELL": -1}
    combined = signal_map.get(tech_signal, 0) + signal_map.get(fund_signal, 0)

    if combined >= 2:
        overall = "STRONG BUY"
    elif combined == 1:
        overall = "BUY"
    elif combined == -1:
        overall = "SELL"
    elif combined <= -2:
        overall = "STRONG SELL"
    else:
        overall = "HOLD"

    report["overall_recommendation"] = overall

    return report


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def print_report(report: dict) -> None:
    """Pretty-print the analysis report to stdout."""
    print("\n" + "=" * 60)
    print(f"  STOCK ANALYSIS REPORT — {report['ticker']}")
    print(f"  Generated: {report['generated_at']}")
    print("=" * 60)

    # Technical section
    tech = report.get("technical", {})
    if "error" not in tech:
        print(f"\n--- Technical Analysis ---")
        print(f"  Price:            ${tech['current_price']}")
        print(f"  RSI:              {tech['rsi']}")
        print(f"  MACD Histogram:   {tech['macd']['histogram']}")
        print(f"  ATR:              {tech['atr']}")
        print(f"  Signal:           {tech['technical_signal']} (score {tech['technical_score']})")
        print(f"  Reasons:")
        for r in tech.get("reasons", []):
            print(f"    • {r}")
    else:
        print(f"\n  Technical: {tech['error']}")

    # Fundamental section
    fund = report.get("fundamental", {})
    if "error" not in fund:
        print(f"\n--- Fundamental Analysis ---")
        metrics = fund.get("metrics", {})
        for key, val in metrics.items():
            print(f"  {key:20s}: {val}")
        print(f"  Signal:           {fund.get('fundamental_signal', 'N/A')} (score {fund.get('fundamental_score', 'N/A')})")
        print(f"  Reasons:")
        for r in fund.get("reasons", []):
            print(f"    • {r}")
    else:
        print(f"\n  Fundamental: {fund['error']}")

    # Sector comparison
    sector = report.get("sector_comparison", {})
    if "error" not in sector:
        print(f"\n--- Sector Comparison ---")
        print(f"  Sector:           {sector.get('sector', 'N/A')}")
        print(f"  Rank:             {sector.get('rank', 'N/A')}")
        print(f"  Peer count:       {sector.get('peer_count', 'N/A')}")
        outperformance = sector.get("outperformance_pct")
        if outperformance is not None:
            print(f"  vs Sector Avg:    {outperformance:+.1f}%")

    # Overall
    print(f"\n{'=' * 60}")
    print(f"  OVERALL RECOMMENDATION:  {report['overall_recommendation']}")
    print(f"{'=' * 60}\n")


def save_report(report: dict, output_dir: str = "reports") -> str:
    """Save report as JSON and return the file path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out / f"{report['ticker']}_{ts}.json"
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info("Report saved to %s", path)
    return str(path)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Stock Analysis Agent — fundamental + technical analysis"
    )
    parser.add_argument(
        "tickers",
        nargs="+",
        help="One or more stock ticker symbols (e.g. AAPL MSFT GOOG)",
    )
    parser.add_argument(
        "--period",
        default=None,
        help="Price history period (default from config, e.g. 1y, 6mo, 3mo)",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Save JSON reports to the reports/ directory",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON instead of formatted output",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to an alternative config.json",
    )
    args = parser.parse_args()

    # Load config
    global CONFIG_PATH
    if args.config:
        CONFIG_PATH = Path(args.config)
    config = load_config()

    if args.period:
        config["default_period"] = args.period

    for ticker in args.tickers:
        ticker = ticker.upper()
        try:
            report = generate_report(ticker, config)

            if args.json:
                print(json.dumps(report, indent=2, default=str))
            else:
                print_report(report)

            if args.save:
                save_report(report)

        except Exception as exc:
            logger.error("Failed to analyse %s: %s", ticker, exc)
            if logger.isEnabledFor(logging.DEBUG):
                logger.exception(exc)


if __name__ == "__main__":
    main()

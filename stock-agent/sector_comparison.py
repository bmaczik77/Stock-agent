#!/usr/bin/env python3
"""
Sector Comparison Tool — compare a stock against its sector peers.

Fetches peer tickers from Yahoo Finance, gathers key metrics, and
ranks the target stock within its sector.
"""

import logging
from statistics import mean, median

import yfinance as yf

logger = logging.getLogger(__name__)

# Fallback peer lists when Yahoo Finance doesn't provide them.
DEFAULT_SECTOR_PEERS: dict[str, list[str]] = {
    "Technology": ["AAPL", "MSFT", "GOOG", "META", "NVDA", "AVGO", "ORCL", "CRM", "ADBE", "INTC"],
    "Healthcare": ["JNJ", "UNH", "PFE", "ABBV", "MRK", "TMO", "ABT", "LLY", "BMY", "AMGN"],
    "Financial Services": ["JPM", "BAC", "WFC", "GS", "MS", "BLK", "SCHW", "AXP", "C", "USB"],
    "Consumer Cyclical": ["AMZN", "TSLA", "HD", "NKE", "MCD", "SBUX", "LOW", "TJX", "BKNG", "CMG"],
    "Communication Services": ["GOOG", "META", "DIS", "NFLX", "CMCSA", "T", "VZ", "TMUS", "CHTR", "EA"],
    "Consumer Defensive": ["PG", "KO", "PEP", "WMT", "COST", "PM", "EL", "CL", "MDLZ", "GIS"],
    "Energy": ["XOM", "CVX", "COP", "SLB", "EOG", "MPC", "PSX", "VLO", "OXY", "WMB"],
    "Industrials": ["HON", "UPS", "UNP", "BA", "CAT", "GE", "MMM", "LMT", "RTX", "DE"],
    "Utilities": ["NEE", "DUK", "SO", "D", "AEP", "SRE", "EXC", "XEL", "ED", "WEC"],
    "Real Estate": ["AMT", "PLD", "CCI", "EQIX", "SPG", "O", "PSA", "WELL", "DLR", "AVB"],
    "Basic Materials": ["LIN", "APD", "SHW", "ECL", "DD", "NEM", "FCX", "NUE", "DOW", "PPG"],
}


class SectorComparison:
    """Compare a stock's key metrics to sector peers."""

    def __init__(self, config: dict | None = None):
        cfg = (config or {}).get("sector_comparison", {})
        self.max_peers = cfg.get("max_peers", 10)
        self.metrics_to_compare = cfg.get(
            "metrics",
            [
                "trailingPE",
                "forwardPE",
                "priceToBook",
                "profitMargins",
                "returnOnEquity",
                "revenueGrowth",
                "debtToEquity",
            ],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compare(self, ticker: str) -> dict:
        """Return comparison data: target metrics, peer averages, rank."""
        logger.info("Running sector comparison for %s", ticker)
        stock = yf.Ticker(ticker)

        try:
            info = stock.info
            if not info:
                raise ValueError("empty response")
        except Exception as exc:
            return {"error": f"Could not fetch info for {ticker}: {exc}"}

        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")

        # Determine peer list
        peers = self._get_peers(ticker, sector)
        if not peers:
            return {
                "error": f"No peers found for {ticker} in sector '{sector}'",
                "sector": sector,
            }

        # Gather metrics for target and peers
        target_metrics = self._gather_metrics(info)
        peer_data = self._fetch_peer_metrics(peers, ticker)

        if not peer_data:
            return {
                "error": "Could not retrieve metrics for any peers",
                "sector": sector,
            }

        # Compute averages and rank
        comparison = self._build_comparison(target_metrics, peer_data)
        rank = self._compute_rank(target_metrics, peer_data)

        # Outperformance vs sector average return
        target_rg = target_metrics.get("revenueGrowth")
        avg_rg = comparison.get("revenueGrowth", {}).get("sector_avg")
        outperformance = None
        if target_rg is not None and avg_rg is not None and avg_rg != 0:
            outperformance = round((target_rg - avg_rg) * 100, 2)

        return {
            "ticker": ticker,
            "sector": sector,
            "industry": industry,
            "peer_count": len(peer_data),
            "peers_analysed": list(peer_data.keys()),
            "target_metrics": {k: _fmt(v) for k, v in target_metrics.items()},
            "comparison": comparison,
            "rank": rank,
            "outperformance_pct": outperformance,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get_peers(self, ticker: str, sector: str) -> list[str]:
        """Return a list of peer tickers for the given sector."""
        peers = DEFAULT_SECTOR_PEERS.get(sector, [])
        # Remove the target itself from the list
        peers = [p for p in peers if p.upper() != ticker.upper()]
        return peers[: self.max_peers]

    def _gather_metrics(self, info: dict) -> dict:
        """Extract the comparison metrics from a stock info dict."""
        return {
            key: info.get(key) for key in self.metrics_to_compare
        }

    def _fetch_peer_metrics(self, peers: list[str], exclude: str) -> dict:
        """Download metrics for each peer. Returns {ticker: {metric: val}}."""
        result = {}
        for peer in peers:
            if peer.upper() == exclude.upper():
                continue
            try:
                info = yf.Ticker(peer).info
                if info:
                    result[peer] = self._gather_metrics(info)
            except Exception:
                logger.debug("Skipping peer %s — data unavailable", peer)
        return result

    def _build_comparison(self, target: dict, peer_data: dict) -> dict:
        """For each metric, compute sector avg/median and delta."""
        comparison = {}
        for metric in self.metrics_to_compare:
            values = [
                pd[metric]
                for pd in peer_data.values()
                if pd.get(metric) is not None
            ]
            target_val = target.get(metric)
            if not values:
                continue

            avg = mean(values)
            med = median(values)

            entry = {
                "target": _fmt(target_val),
                "sector_avg": round(avg, 4),
                "sector_median": round(med, 4),
            }
            if target_val is not None:
                entry["vs_avg"] = round(target_val - avg, 4)
                entry["vs_avg_pct"] = (
                    round((target_val - avg) / abs(avg) * 100, 2)
                    if avg != 0
                    else None
                )
            comparison[metric] = entry
        return comparison

    def _compute_rank(self, target: dict, peer_data: dict) -> dict:
        """Rank the target among peers for each metric (1 = best)."""
        rankings = {}
        for metric in self.metrics_to_compare:
            target_val = target.get(metric)
            if target_val is None:
                continue

            all_vals = [(ticker, pd.get(metric)) for ticker, pd in peer_data.items()]
            all_vals = [(t, v) for t, v in all_vals if v is not None]
            all_vals.append(("TARGET", target_val))

            # Higher is better for profitability/growth; lower is better for
            # valuation and debt.
            higher_is_better = metric in {
                "profitMargins",
                "returnOnEquity",
                "revenueGrowth",
            }
            all_vals.sort(key=lambda x: x[1], reverse=higher_is_better)
            rank = next(
                i + 1 for i, (t, _) in enumerate(all_vals) if t == "TARGET"
            )
            rankings[metric] = {
                "rank": rank,
                "out_of": len(all_vals),
            }
        return rankings


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _fmt(val):
    """Format a value for display — round floats, pass through others."""
    if isinstance(val, float):
        return round(val, 4)
    return val

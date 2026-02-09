#!/usr/bin/env python3
"""
Fundamental Analyzer — deep-dive into a company's financial health.

Pulls key financial metrics from Yahoo Finance and scores them to
produce a fundamental BUY / HOLD / SELL signal.
"""

import logging

import yfinance as yf

logger = logging.getLogger(__name__)


class FundamentalAnalyzer:
    """Evaluate a stock's fundamentals using valuation, profitability,
    growth, and balance-sheet metrics."""

    # Default thresholds — can be overridden via config.json
    DEFAULTS = {
        "pe_ratio_low": 15,
        "pe_ratio_high": 30,
        "peg_ratio_threshold": 1.5,
        "profit_margin_good": 0.15,
        "profit_margin_poor": 0.05,
        "debt_to_equity_low": 0.5,
        "debt_to_equity_high": 2.0,
        "current_ratio_good": 1.5,
        "current_ratio_poor": 1.0,
        "roe_good": 0.15,
        "roe_poor": 0.08,
        "revenue_growth_good": 0.10,
        "revenue_growth_poor": 0.0,
        "free_cashflow_positive": True,
        "dividend_yield_good": 0.02,
    }

    def __init__(self, config: dict | None = None):
        cfg = (config or {}).get("fundamental_analysis", {})
        self.thresholds = {**self.DEFAULTS, **cfg}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, ticker: str) -> dict:
        """Return a dict with metrics, score, signal, and reasoning."""
        logger.info("Running fundamental analysis for %s", ticker)
        stock = yf.Ticker(ticker)

        try:
            info = stock.info
            if not info:
                raise ValueError("empty response")
        except Exception as exc:
            return {"error": f"Could not fetch info for {ticker}: {exc}"}

        if not info:
            return {"error": f"No fundamental data available for {ticker}"}

        metrics = self._extract_metrics(info)
        score, reasons = self._score(metrics)

        if score >= 3:
            signal = "BUY"
        elif score <= -2:
            signal = "SELL"
        else:
            signal = "HOLD"

        return {
            "ticker": ticker,
            "company_name": info.get("longName", "N/A"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "metrics": metrics,
            "fundamental_score": score,
            "fundamental_signal": signal,
            "reasons": reasons,
        }

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _safe(info: dict, key: str, default=None):
        """Safely retrieve a value from the info dict."""
        val = info.get(key, default)
        if val is None:
            return default
        return val

    def _extract_metrics(self, info: dict) -> dict:
        """Pull relevant financial metrics into a flat dict."""
        return {
            "pe_ratio": self._safe(info, "trailingPE"),
            "forward_pe": self._safe(info, "forwardPE"),
            "peg_ratio": self._safe(info, "pegRatio"),
            "price_to_book": self._safe(info, "priceToBook"),
            "price_to_sales": self._safe(info, "priceToSalesTrailing12Months"),
            "profit_margin": self._safe(info, "profitMargins"),
            "operating_margin": self._safe(info, "operatingMargins"),
            "roe": self._safe(info, "returnOnEquity"),
            "roa": self._safe(info, "returnOnAssets"),
            "debt_to_equity": self._safe(info, "debtToEquity"),
            "current_ratio": self._safe(info, "currentRatio"),
            "quick_ratio": self._safe(info, "quickRatio"),
            "revenue_growth": self._safe(info, "revenueGrowth"),
            "earnings_growth": self._safe(info, "earningsGrowth"),
            "free_cashflow": self._safe(info, "freeCashflow"),
            "dividend_yield": self._safe(info, "dividendYield"),
            "market_cap": self._safe(info, "marketCap"),
            "enterprise_value": self._safe(info, "enterpriseValue"),
            "ev_to_ebitda": self._safe(info, "enterpriseToEbitda"),
            "ev_to_revenue": self._safe(info, "enterpriseToRevenue"),
            "beta": self._safe(info, "beta"),
            "52w_high": self._safe(info, "fiftyTwoWeekHigh"),
            "52w_low": self._safe(info, "fiftyTwoWeekLow"),
        }

    def _score(self, m: dict) -> tuple[int, list[str]]:
        """Score the metrics and collect human-readable reasons."""
        t = self.thresholds
        score = 0
        reasons: list[str] = []

        # --- Valuation ---
        pe = m.get("pe_ratio")
        if pe is not None:
            if pe < t["pe_ratio_low"]:
                score += 1
                reasons.append(f"P/E ({pe:.1f}) below {t['pe_ratio_low']} — potentially undervalued")
            elif pe > t["pe_ratio_high"]:
                score -= 1
                reasons.append(f"P/E ({pe:.1f}) above {t['pe_ratio_high']} — potentially overvalued")
            else:
                reasons.append(f"P/E ({pe:.1f}) in fair-value range")

        peg = m.get("peg_ratio")
        if peg is not None:
            if peg < t["peg_ratio_threshold"]:
                score += 1
                reasons.append(f"PEG ({peg:.2f}) below {t['peg_ratio_threshold']} — good growth value")
            else:
                score -= 1
                reasons.append(f"PEG ({peg:.2f}) above {t['peg_ratio_threshold']} — growth may be priced in")

        # --- Profitability ---
        pm = m.get("profit_margin")
        if pm is not None:
            if pm > t["profit_margin_good"]:
                score += 1
                reasons.append(f"Profit margin ({pm:.1%}) is strong")
            elif pm < t["profit_margin_poor"]:
                score -= 1
                reasons.append(f"Profit margin ({pm:.1%}) is weak")

        roe = m.get("roe")
        if roe is not None:
            if roe > t["roe_good"]:
                score += 1
                reasons.append(f"ROE ({roe:.1%}) is healthy")
            elif roe < t["roe_poor"]:
                score -= 1
                reasons.append(f"ROE ({roe:.1%}) is below par")

        # --- Balance sheet ---
        de = m.get("debt_to_equity")
        if de is not None:
            # yfinance returns D/E as a percentage (e.g. 150 = 1.5x)
            de_ratio = de / 100 if de > 10 else de
            if de_ratio < t["debt_to_equity_low"]:
                score += 1
                reasons.append(f"Low debt-to-equity ({de_ratio:.2f})")
            elif de_ratio > t["debt_to_equity_high"]:
                score -= 1
                reasons.append(f"High debt-to-equity ({de_ratio:.2f})")

        cr = m.get("current_ratio")
        if cr is not None:
            if cr > t["current_ratio_good"]:
                score += 1
                reasons.append(f"Strong current ratio ({cr:.2f})")
            elif cr < t["current_ratio_poor"]:
                score -= 1
                reasons.append(f"Weak current ratio ({cr:.2f})")

        # --- Growth ---
        rg = m.get("revenue_growth")
        if rg is not None:
            if rg > t["revenue_growth_good"]:
                score += 1
                reasons.append(f"Revenue growth ({rg:.1%}) is solid")
            elif rg < t["revenue_growth_poor"]:
                score -= 1
                reasons.append(f"Revenue declining ({rg:.1%})")

        # --- Cash flow ---
        fcf = m.get("free_cashflow")
        if fcf is not None:
            if fcf > 0:
                score += 1
                reasons.append(f"Positive free cash flow (${fcf:,.0f})")
            else:
                score -= 1
                reasons.append(f"Negative free cash flow (${fcf:,.0f})")

        # --- Dividend ---
        dy = m.get("dividend_yield")
        if dy is not None and dy > t["dividend_yield_good"]:
            score += 1
            reasons.append(f"Attractive dividend yield ({dy:.2%})")

        return score, reasons

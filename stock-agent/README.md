# Stock Analysis Agent

A Python-based stock analysis tool that combines **fundamental analysis** and **technical analysis** to generate comprehensive reports with actionable BUY / HOLD / SELL recommendations.

## Features

- **Technical Analysis** — SMA, EMA, RSI, MACD, Bollinger Bands, ATR, OBV
- **Fundamental Analysis** — P/E, PEG, profit margins, ROE, debt-to-equity, free cash flow, and more
- **Sector Comparison** — rank a stock against its sector peers across key metrics
- **Combined Signal** — merges technical and fundamental scores into a single recommendation
- **Scheduler** — automate daily analysis for a configurable watchlist
- **JSON Reports** — save structured reports for downstream processing

## Quick Start

```bash
# 1. Run the setup script (creates a venv and installs dependencies)
chmod +x setup.sh
./setup.sh

# 2. Activate the virtual environment
source venv/bin/activate

# 3. Analyse one or more tickers
python agent.py AAPL MSFT GOOG --save
```

## Usage

```
python agent.py [-h] [--period PERIOD] [--save] [--json] [--config CONFIG] tickers [tickers ...]
```

| Argument | Description |
|---|---|
| `tickers` | One or more stock ticker symbols (e.g. `AAPL MSFT`) |
| `--period` | Price history period (`1y`, `6mo`, `3mo`, etc.) |
| `--save` | Save JSON reports to `reports/` |
| `--json` | Print raw JSON output instead of formatted text |
| `--config` | Path to an alternative `config.json` |

### Examples

```bash
# Quick analysis printed to the terminal
python agent.py TSLA

# Analyse multiple stocks and save JSON reports
python agent.py AAPL MSFT GOOG AMZN --save

# Use a shorter lookback period
python agent.py NVDA --period 6mo

# Get raw JSON (useful for piping into other tools)
python agent.py AAPL --json | jq .overall_recommendation
```

## Scheduler

Run automated daily analysis at a configured time:

```bash
# Start the scheduler (runs daily at the time in config.json)
python scheduler.py

# Run immediately and then continue on schedule
python scheduler.py --now
```

Configure the watchlist and schedule in `config.json` under the `"scheduler"` key.

## Configuration

All thresholds and settings live in `config.json`:

| Section | What it controls |
|---|---|
| `technical_analysis` | SMA/EMA periods, RSI period, MACD params, Bollinger settings |
| `fundamental_analysis` | Valuation thresholds (P/E, PEG), profitability targets, debt limits |
| `sector_comparison` | Max peers to compare, which metrics to use |
| `scheduler` | Watchlist, daily run time, timezone, email notification settings |

## Project Structure

```
stock-agent/
├── agent.py                 # Main entry point — CLI and combined report
├── fundamental_analyzer.py  # Deep-dive fundamental analysis
├── sector_comparison.py     # Peer comparison tool
├── scheduler.py             # Daily automation
├── config.json              # All configurable thresholds and settings
├── requirements.txt         # Python dependencies
├── setup.sh                 # One-command environment setup
└── README.md                # This file
```

## How Scoring Works

### Technical Score

| Indicator | Bullish (+1) | Bearish (−1) |
|---|---|---|
| SMA 50 vs 200 | Golden cross | Death cross |
| RSI | Below 30 (oversold) | Above 70 (overbought) |
| MACD histogram | Positive | Negative |
| Bollinger Bands | Price below lower band | Price above upper band |

### Fundamental Score

Metrics like P/E, PEG, profit margin, ROE, debt-to-equity, revenue growth, and free cash flow are each scored +1 (good) or −1 (poor) against configurable thresholds.

### Combined Recommendation

| Combined Score | Signal |
|---|---|
| ≥ 2 | STRONG BUY |
| 1 | BUY |
| 0 | HOLD |
| −1 | SELL |
| ≤ −2 | STRONG SELL |

## Dependencies

- [yfinance](https://github.com/ranaroussi/yfinance) — Yahoo Finance market data
- [pandas](https://pandas.pydata.org/) — data manipulation
- [numpy](https://numpy.org/) — numerical computation
- [schedule](https://schedule.readthedocs.io/) — lightweight job scheduling

## License

MIT

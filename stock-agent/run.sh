#!/usr/bin/env bash
#
# run.sh — install dependencies if needed and run the stock analysis agent.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"

# Bootstrap if venv doesn't exist yet
if [ ! -d "$VENV_DIR" ]; then
    echo "First run — setting up environment..."
    bash "$SCRIPT_DIR/setup.sh"
fi

# Activate venv
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Pass through any CLI arguments, defaulting to the config watchlist
if [ $# -eq 0 ]; then
    echo "No tickers specified — using watchlist from config.json"
    TICKERS=$(python3 -c "import json; cfg=json.load(open('$SCRIPT_DIR/config.json')); print(' '.join(cfg.get('scheduler',{}).get('watchlist',[])))")
    if [ -z "$TICKERS" ]; then
        echo "ERROR: No tickers in config watchlist. Pass tickers as arguments:"
        echo "  ./run.sh AAPL MSFT GOOG"
        exit 1
    fi
    python3 "$SCRIPT_DIR/agent.py" $TICKERS --save
else
    python3 "$SCRIPT_DIR/agent.py" "$@"
fi

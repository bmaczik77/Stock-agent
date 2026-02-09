#!/usr/bin/env bash
#
# setup.sh — bootstrap the Stock Analysis Agent environment.
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"

echo "============================================"
echo "  Stock Analysis Agent — Setup"
echo "============================================"
echo

# ------------------------------------------------------------------
# 1. Check Python version
# ------------------------------------------------------------------
PYTHON=""
for candidate in python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" &>/dev/null; then
        PYTHON="$candidate"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "ERROR: Python 3.10+ is required but not found."
    echo "       Install Python from https://www.python.org/downloads/"
    exit 1
fi

PY_VERSION=$("$PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$("$PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$PYTHON" -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 10 ]; }; then
    echo "ERROR: Python 3.10+ is required (found $PY_VERSION)."
    exit 1
fi

echo "[1/4] Using $PYTHON ($PY_VERSION)"

# ------------------------------------------------------------------
# 2. Create virtual environment
# ------------------------------------------------------------------
if [ -d "$VENV_DIR" ]; then
    echo "[2/4] Virtual environment already exists at $VENV_DIR"
else
    echo "[2/4] Creating virtual environment at $VENV_DIR ..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# ------------------------------------------------------------------
# 3. Upgrade pip and install dependencies
# ------------------------------------------------------------------
echo "[3/4] Installing dependencies ..."
pip install --upgrade pip --quiet
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet

# ------------------------------------------------------------------
# 4. Verify installation
# ------------------------------------------------------------------
echo "[4/4] Verifying installation ..."
"$PYTHON" -c "
import yfinance, pandas, numpy, schedule
print(f'  yfinance  {yfinance.__version__}')
print(f'  pandas    {pandas.__version__}')
print(f'  numpy     {numpy.__version__}')
print(f'  schedule  {schedule.__version__}')
"

echo
echo "============================================"
echo "  Setup complete!"
echo "============================================"
echo
echo "Activate the environment:"
echo "  source $VENV_DIR/bin/activate"
echo
echo "Run an analysis:"
echo "  python agent.py AAPL MSFT --save"
echo
echo "Start the scheduler:"
echo "  python scheduler.py"
echo

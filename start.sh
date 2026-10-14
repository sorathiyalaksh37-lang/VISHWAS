#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN=""
if [ -f "/opt/anaconda3/bin/python3" ]; then
    PYTHON_BIN="/opt/anaconda3/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="$(command -v python3)"
else
    PYTHON_BIN="python"
fi
"$PYTHON_BIN" "$DIR/start.py"

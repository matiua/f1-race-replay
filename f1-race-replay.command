#!/bin/bash
# Double-click this file to set up and launch F1 Race Replay.
# First run: clones the repo and installs dependencies (~1 min).
# Later runs: pulls updates and launches instantly.

set -e

INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)/f1-race-replay"
REPO_URL="https://github.com/matiua/f1-race-replay-app"

echo "============================================"
echo "        F1 Race Replay - Launcher"
echo "============================================"
echo ""

# Check Python 3.10+
if ! command -v python3 &>/dev/null; then
    echo "ERROR: Python 3 is not installed."
    echo ""
    echo "Install Python 3.11 from: https://www.python.org/downloads/"
    echo "Then double-click this file again."
    read -p "Press Enter to close..."
    exit 1
fi

PY_VERSION=$(python3 -c "import sys; print(sys.version_info.minor + sys.version_info.major * 100)")
if [ "$PY_VERSION" -lt 310 ]; then
    CURRENT=$(python3 --version)
    echo "ERROR: Python 3.10 or newer is required."
    echo "You have: $CURRENT"
    echo ""
    echo "Download Python 3.11 from: https://www.python.org/downloads/"
    echo "Install it, then double-click this file again."
    read -p "Press Enter to close..."
    exit 1
fi

# Check Git
if ! command -v git &>/dev/null; then
    echo "ERROR: Git is not installed."
    echo ""
    echo "Install it by running in Terminal:  xcode-select --install"
    echo "Then double-click this file again."
    read -p "Press Enter to close..."
    exit 1
fi

# Clone or update
if [ ! -d "$INSTALL_DIR" ]; then
    echo "[1/4] Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
else
    # An existing folder may have been cloned from an older/different remote
    # (e.g. before this repo existed). `git pull` silently pulls from
    # whatever remote is already configured, not from REPO_URL, so fix the
    # remote first if it doesn't match.
    CURRENT_URL="$(git -C "$INSTALL_DIR" remote get-url origin 2>/dev/null | sed -E 's#/$##; s#\.git$##')"
    WANTED_URL="$(echo "$REPO_URL" | sed -E 's#/$##; s#\.git$##')"
    if [ "$CURRENT_URL" != "$WANTED_URL" ]; then
        echo "[1/4] Existing folder points at a different repo ($CURRENT_URL). Fixing remote..."
        git -C "$INSTALL_DIR" remote set-url origin "$REPO_URL"
    fi
    echo "[1/4] Pulling latest updates..."
    git -C "$INSTALL_DIR" pull
fi

# Create venv
if [ ! -d "$INSTALL_DIR/venv" ]; then
    echo "[2/4] Creating virtual environment..."
    python3 -m venv "$INSTALL_DIR/venv"
else
    echo "[2/4] Virtual environment ready."
fi

# Install dependencies
echo "[3/4] Installing dependencies (first run takes ~1 min)..."
"$INSTALL_DIR/venv/bin/pip" install --quiet -r "$INSTALL_DIR/requirements.txt"

# Launch
echo "[4/4] Launching F1 Race Replay..."
echo ""
"$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/main.py"

echo ""
read -p "App closed. Press Enter to exit."

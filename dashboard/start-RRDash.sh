#!/bin/bash
# start-RRDash — launches the Reframing Reality manuscript dashboard
# Opens http://127.0.0.1:8765 in your default browser.
# Press Ctrl-C in this terminal to stop the server.

set -e

VAULT="/Users/peterduke/Documents/Reframing Reality Vault"
PORT=8765
URL="http://127.0.0.1:${PORT}"

if [ ! -f "$VAULT/dashboard.py" ]; then
    echo "Error: dashboard.py not found in $VAULT"
    echo "The dashboard script should live at: $VAULT/dashboard.py"
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 not found on PATH."
    echo "Install Python 3 from python.org or via Homebrew (brew install python)."
    exit 1
fi

echo "Reframing Reality — manuscript dashboard"
echo "  Vault:   $VAULT"
echo "  URL:     $URL"
echo "  Browser: will open shortly"
echo "  Stop:    Ctrl-C"
echo

# Open the browser ~1.5s after the server starts (gives it time to bind the port).
( sleep 1.5 && open "$URL" ) &

cd "$VAULT"
# Pin the native arm64 slice (see the plist comment): a universal2 python3 can
# otherwise run x86 under Rosetta and hand that architecture down to rag-ui,
# whose arm64 torch/faiss wheels then fail to load.
exec arch -arm64 python3 dashboard.py

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

PYBIN="/opt/homebrew/bin/python3"   # arm64-only — never runs under Rosetta
if [ ! -x "$PYBIN" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYBIN="$(command -v python3)"   # fallback; may be universal
    else
        echo "Error: python3 not found (looked for $PYBIN, then PATH)."
        echo "Install via Homebrew (brew install python) or python.org."
        exit 1
    fi
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
# Prefer the arm64-only interpreter so this can never run under Rosetta (a stale
# x86 dashboard triggered the "Intel-based Apps" nag on 2026-09-29). arch -arm64
# is kept as belt-and-suspenders even though $PYBIN normally has no Intel slice.
exec arch -arm64 "$PYBIN" dashboard.py

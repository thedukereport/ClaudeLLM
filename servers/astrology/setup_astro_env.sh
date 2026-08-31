#!/bin/bash
# setup_astro_env.sh — create the Python environment the astrology MCP server needs.
#
# The astrology server is the one MCP server that needs a third-party package
# (kerykeion, which bundles the Swiss Ephemeris via pyswisseph). It gets its own
# venv so it doesn't touch the RAG or other environments.
#
#     bash /Volumes/PRO-BLADE/Astrology/setup_astro_env.sh
#
set -euo pipefail
DIR="/Volumes/PRO-BLADE/Astrology"

# Prefer the native arm64 Homebrew Python (no Rosetta / Intel-Python nagging).
PY="/opt/homebrew/bin/python3"
[ -x "$PY" ] || PY="$(command -v python3)"
echo "Using Python: $PY"

"$PY" -m venv "$DIR/astro_env"
"$DIR/astro_env/bin/python" -m pip install --upgrade pip wheel >/dev/null
echo "Installing kerykeion (+ pyswisseph)… this fetches a few packages."
"$DIR/astro_env/bin/python" -m pip install -r "$DIR/requirements.txt"

echo "--- verify ---"
"$DIR/astro_env/bin/python" - <<'PY'
import platform, kerykeion
from kerykeion import AstrologicalSubjectFactory as F, NatalAspects
s = F.from_birth_data("Test", 2000, 1, 1, 12, 0, lat=51.48, lng=0.0,
                      tz_str="Etc/GMT", online=False, suppress_geonames_warning=True)
print("machine:", platform.machine(), "| kerykeion OK | Sun:",
      s.model_dump()["sun"]["sign"], round(s.model_dump()["sun"]["position"], 1))
PY

cat <<EOF

=====================  SUCCESS  =====================
astro_env is ready. Add this to Claude Desktop's mcpServers config:

  "astrology": {
    "command": "$DIR/astro_env/bin/python",
    "args": ["$DIR/astrology_mcp_server.py"]
  }

Then fully quit and reopen Claude Desktop.
=====================================================
EOF

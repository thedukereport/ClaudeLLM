#!/bin/bash
# ---------------------------------------------------------------------------
# migrate_rag_env_arm64.sh
#
# Rebuild rag_env on Homebrew's ARM64-ONLY Python 3.10 so macOS stops flagging
# the python.org ("Intel-based") Python. Fixes rag-ui AND all MCP servers at
# once, since they share rag_env.
#
# SAFE BY DESIGN:
#   * captures the EXACT versions you're running now (pip freeze) and reinstalls
#     those, so nothing changes but the interpreter underneath;
#   * keeps your current venv as rag_env.intel-backup and does NOT delete it;
#   * if any step fails, it automatically restores the original venv.
#
# Run it with the servers stopped:
#   bash /Volumes/PRO-BLADE/Alexandria/RAG_system/migrate_rag_env_arm64.sh
# ---------------------------------------------------------------------------
set -euo pipefail

RAG=/Volumes/PRO-BLADE/Alexandria/RAG_system
BREW_PY=/opt/homebrew/bin/python3.10
cd "$RAG"

echo "== 1/6  Ensure Homebrew arm64 Python 3.10 =="
# IMPORTANT: use the ARM64 Homebrew at /opt/homebrew explicitly. On this Mac the
# bare `brew` on PATH is the *Intel* Homebrew at /usr/local, which would install
# an x86 Python — the exact thing we're trying to get away from.
ARM_BREW=/opt/homebrew/bin/brew
if [ ! -x "$BREW_PY" ]; then
  if [ ! -x "$ARM_BREW" ]; then
    echo "   ✗ arm64 Homebrew not found at $ARM_BREW — aborting (nothing changed)."; exit 1
  fi
  echo "   python@3.10 not found — installing via ARM64 Homebrew (a few minutes)..."
  arch -arm64 "$ARM_BREW" install python@3.10
fi
if file "$(readlink -f "$BREW_PY")" | grep -q arm64; then
  echo "   OK: $BREW_PY is native arm64"
else
  echo "   ✗ $BREW_PY is not arm64 — aborting (nothing changed)."; exit 1
fi

echo "== 2/6  Capture the exact versions you run today =="
FREEZE="/tmp/rag-freeze-$(date +%Y%m%d-%H%M%S).txt"
"$RAG/rag_env/bin/python" -m pip freeze > "$FREEZE"
echo "   wrote $FREEZE ($(wc -l < "$FREEZE" | tr -d ' ') packages)"

echo "== 3/6  Back up the current (Intel) venv =="
if [ -d rag_env.intel-backup ]; then
  echo "   ✗ rag_env.intel-backup already exists. Remove or rename it first, then re-run."; exit 1
fi
mv rag_env rag_env.intel-backup
echo "   moved rag_env → rag_env.intel-backup"

# From here on, restore the original venv if anything goes wrong.
restore() {
  echo ""
  echo "!! A step failed — restoring your original venv so nothing is lost."
  rm -rf "$RAG/rag_env"
  mv "$RAG/rag_env.intel-backup" "$RAG/rag_env"
  echo "   restored. Your system is exactly as before. No harm done."
}
trap restore ERR

echo "== 4/6  Create the new arm64 venv =="
"$BREW_PY" -m venv rag_env
rag_env/bin/python -m pip install --upgrade pip wheel >/dev/null
echo "   new venv created with $BREW_PY"

echo "== 5/6  Reinstall the same versions (this downloads ~1 GB, a few minutes) =="
rag_env/bin/python -m pip install -r "$FREEZE"

echo "== 6/6  Verify native arm64 + GPU + key imports =="
rag_env/bin/python - <<'PY'
import platform, torch, faiss, sentence_transformers as st, numpy
assert platform.machine() == "arm64", f"NOT arm64: {platform.machine()}"
print("   machine :", platform.machine())
print("   python  :", platform.python_version())
print("   torch   :", torch.__version__, "| MPS:", torch.backends.mps.is_available())
print("   faiss   : import OK")
print("   sent-tf :", st.__version__)
print("   numpy   :", numpy.__version__)
PY

trap - ERR
cat <<EOF

=====================  SUCCESS  =====================
rag_env now runs on native arm64 Python — the "Intel-based Python" alert
will stop, for rag-ui and every MCP server.

Your old environment is preserved at:
   rag_env.intel-backup

NEXT STEPS
  1) Restart the dashboard so it re-launches things on the new venv:
       launchctl kickstart -k gui/\$(id -u)/com.dukemedia.rrdash
  2) In the dashboard, Start rag-ui and run a test search.
  3) Restart Claude Desktop so the MCP servers relaunch on the new venv.
  4) Once everything works, delete the backup to reclaim ~1 GB:
       rm -rf "$RAG/rag_env.intel-backup"

If anything misbehaves, roll back instantly:
       rm -rf "$RAG/rag_env" && mv "$RAG/rag_env.intel-backup" "$RAG/rag_env"
=====================================================
EOF

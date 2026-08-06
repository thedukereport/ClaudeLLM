#!/bin/bash
# Run Alexandria RAG Web UI

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "======================================"
echo "Alexandria RAG - Web UI"
echo "======================================"

# Check if virtual environment exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Virtual environment not found."
    echo "Running setup..."
    cd "$SCRIPT_DIR"
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source "$SCRIPT_DIR/venv/bin/activate"
fi

echo ""
echo "Starting web UI..."
echo "Access it at: http://127.0.0.1:5050"
echo ""
echo "Press Ctrl+C to stop"
echo ""

cd "$SCRIPT_DIR"
python app.py

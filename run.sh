#!/bin/bash
# AdLens PK - Environment Activator & Streamlit Launcher

set -e

# Navigate to the repository root directory
cd "$(dirname "$0")"

echo "========================================================"
echo "  Launching AdLens PK — Ad Intelligence Engine          "
echo "========================================================"

# Activate virtual environment if available
if [ -d "venv" ]; then
    echo "[+] Activating virtual environment (venv)..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "[+] Activating virtual environment (.venv)..."
    source .venv/bin/activate
elif [ -d "env" ]; then
    echo "[+] Activating virtual environment (env)..."
    source env/bin/activate
else
    echo "[!] No virtual environment folder found. Using system Python environment."
fi

# Ensure .env exists from template if not already present
if [ ! -f ".env" ] && [ -f ".env.example" ]; then
    echo "[*] Creating .env from .env.example..."
    cp .env.example .env
fi

# Launch the Streamlit application
echo "[+] Starting Streamlit app on http://localhost:8501..."
streamlit run src/ui/app.py

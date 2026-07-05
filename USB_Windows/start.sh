#!/usr/bin/env bash
DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
cd "$DIR"
clear 2>/dev/null || true

cat <<'EOF'
======================================================
     Private Clinic — Obstetrics Management
     Maternity Care · Antenatal Visits · Follow-ups
======================================================

EOF

# ── Run compiled binary directly (zero setup) ──
if [ -f "./OMS" ]; then
    chmod +x ./OMS 2>/dev/null
    xdg-open "http://localhost:5000/dashboard" 2>/dev/null || true
    exec ./OMS
fi

# ── Source mode: find Python ──
echo " [1/2] Checking Python..."
PYTHON_CMD=""
command -v python3 &>/dev/null && PYTHON_CMD="python3"
if [ -z "$PYTHON_CMD" ] && command -v python &>/dev/null; then
    python -c "import sys; exit(0 if sys.version_info.major >= 3 else 1)" &>/dev/null && PYTHON_CMD="python"
fi
if [ -z "$PYTHON_CMD" ]; then
    echo " [ERROR] Python 3 not found!"
    echo " Install Python 3.8+ from https://www.python.org/downloads/"
    read -p " Press Enter to exit..."
    exit 1
fi

mkdir -p data
echo ""
echo " [2/2] Starting application..."
xdg-open "http://localhost:5000/dashboard" 2>/dev/null || true
$PYTHON_CMD run.py
echo ""
read -p " Press Enter to exit..."

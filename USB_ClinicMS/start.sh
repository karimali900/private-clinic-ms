#!/usr/bin/env bash
# ── Detect OS ──
OS="$(uname -s)"

# ── Banner ──
clear 2>/dev/null || true
cat <<'EOF'
======================================================
     Private Clinic — Obstetrics Management
     Maternity Care · Antenatal Visits · Follow-ups
======================================================

EOF

# ── Change to script directory ──
DIR="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || echo "$0")")" && pwd)"
cd "$DIR"

echo " [1/3] Checking Python..."

# ── Find Python 3 ──
PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null && python -c "import sys; exit(0 if sys.version_info.major >= 3 else 1)" &> /dev/null; then
    PYTHON_CMD="python"
fi

if [ -z "$PYTHON_CMD" ]; then
    echo " [ERROR] Python 3 not found!"
    echo ""
    echo " Install it:"
    echo "   Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "   Fedora:        sudo dnf install python3 python3-pip"
    echo "   Arch:          sudo pacman -S python python-pip"
    echo "   macOS:         brew install python"
    echo "                  OR https://www.python.org/downloads/"
    echo ""
    read -p " Press Enter to exit..."
    exit 1
fi

echo " [OK] Found: $($PYTHON_CMD --version 2>&1)"

# ── Check Python version ──
if ! $PYTHON_CMD -c "import sys; exit(0 if sys.version_info>=(3,8) else 1)" &> /dev/null; then
    echo " [ERROR] Python 3.8+ required. Found: $($PYTHON_CMD --version 2>&1)"
    read -p " Press Enter to exit..."
    exit 1
fi

# ── Ensure data folder ──
mkdir -p data

echo ""
echo " [2/3] Starting application..."
echo ""

# ── Open browser (best effort) ──
case "$OS" in
    Darwin)  open "http://localhost:5000/dashboard" 2>/dev/null || true ;;
    *)       xdg-open "http://localhost:5000/dashboard" 2>/dev/null || true ;;
esac

# ── Run main setup + server (handles venv + deps) ──
$PYTHON_CMD run.py

echo ""
read -p " Press Enter to exit..."

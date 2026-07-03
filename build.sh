#!/bin/bash
# Build OMS for Linux — created by Karim Abdelaziz — 00201029927276
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ">> Installing dependencies..."
pip install pyinstaller pyarmor 2>/dev/null || true

echo ""
echo ">> Obfuscating source code with PyArmor..."
pyarmor gen --output obf_dist --recursive run.py Cloud_API.py database.py classification.py Postpartum.py 2>/dev/null

echo ""
echo ">> Building executable with PyInstaller..."
cd obf_dist
pyinstaller --clean --noconfirm --onefile --windowed \
  --name "OMS" \
  --add-data "data:data" \
  --hidden-import "passlib.handlers.pbkdf2_sha256" \
  --hidden-import "passlib.handlers.sha2_crypt" \
  --hidden-import "uvicorn" \
  --hidden-import "uvicorn.logging" \
  --hidden-import "uvicorn.loops.auto" \
  --hidden-import "uvicorn.protocols.http.auto" \
  --hidden-import "uvicorn.protocols.websockets.auto" \
  --hidden-import "uvicorn.middleware.asgi2" \
  --hidden-import "uvicorn.middleware.wsgi" \
  --hidden-import "uvicorn.lifespan.on" \
  --hidden-import "fastapi" \
  --hidden-import "pydantic" \
  --hidden-import "starlette.middleware.cors" \
  --hidden-import "websockets" \
  --hidden-import "websockets.legacy.client" \
  --hidden-import "websockets.legacy.server" \
  --hidden-import "httptools" \
  --hidden-import "database" \
  --hidden-import "multipart" \
  --hidden-import "multipart.multipart" \
  --exclude-module "tkinter" \
  --exclude-module "matplotlib" \
  --exclude-module "scipy" \
  --exclude-module "numpy" \
  --exclude-module "pandas" \
  --exclude-module "PIL" \
  run.py

cd "$DIR"
mkdir -p dist_linux/data
cp obf_dist/dist/OMS dist_linux/
cp -r data/* dist_linux/data/
cp start.sh dist_linux/
cp README.txt dist_linux/
chmod +x dist_linux/OMS dist_linux/start.sh

echo ""
echo "===================================================="
echo "  BUILD COMPLETE!"
echo "  Output: dist_linux/"
echo "  Run: ./dist_linux/start.sh"
echo "===================================================="
echo ""
echo "  Created by Karim Abdelaziz"
echo "  00201029927276"
echo ""

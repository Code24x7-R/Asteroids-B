#!/usr/bin/env bash
# ==============================================================================
# Build WebAssembly Page for Asteroids 3D Holographic UIX (POSIX / CI)
# ==============================================================================
set -euo pipefail

echo "============================================================"
echo "  ASTEROIDS 3D - WEBASSEMBLY BUILD PIPELINE (PYGBAG)"
echo "============================================================"

echo "[1/4] Verifying Pygbag installation..."
if ! python3 -c "import pygbag" 2>/dev/null; then
    echo "Installing pygbag..."
    pip install --upgrade pygbag
fi

echo "[2/4] Compiling WebAssembly package via Pygbag..."
python3 -m pygbag --build --template web/template.tmpl --icon Asteroid.png --app_name asteroids main.py

echo "[3/4] Packaging static output to dist/web/..."
mkdir -p dist/web
cp -r build/web/* dist/web/
[ -f CNAME ] && cp CNAME dist/web/CNAME

echo "[4/4] Creating itch.io web zip archive..."
rm -f dist/asteroids-3d-web.zip
(cd dist/web && zip -r ../asteroids-3d-web.zip ./*)

echo "============================================================"
echo "  BUILD COMPLETE: dist/web/ (artifacts ready)"
echo "============================================================"

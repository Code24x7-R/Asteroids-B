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

echo "[3b/4] Fetching pygame-ce WASM wheel..."
mkdir -p dist/web/cdn/cp312
WHEEL_URL="https://pygame-web.github.io/cdn/cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl"
WHEEL_PATH="dist/web/cdn/cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl"
if [ ! -f "$WHEEL_PATH" ]; then
    echo "Downloading pygame_ce wheel from CDN..."
    curl -L -o "$WHEEL_PATH" "$WHEEL_URL"
    echo "Wheel downloaded: $WHEEL_PATH"
else
    echo "Wheel already exists: $WHEEL_PATH"
fi

echo "[4/4] Creating itch.io web zip archive..."
rm -f dist/asteroids-3d-web.zip
(cd dist/web && zip -r ../asteroids-3d-web.zip ./*)

echo "============================================================"
echo "  BUILD COMPLETE: dist/web/ (artifacts ready)"
echo "============================================================"

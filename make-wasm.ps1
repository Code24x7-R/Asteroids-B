# ==============================================================================
# Build WebAssembly Page for Asteroids 3D Holographic UIX
# ==============================================================================
param(
    [switch]$Serve = $false,
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  ASTEROIDS 3D - WEBASSEMBLY BUILD PIPELINE (PYGBAG)" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Step 1: Ensure Pygbag is installed
Write-Host "`n[1/5] Checking Pygbag runtime..." -ForegroundColor Yellow
$pygbagInstalled = python -c "import pygbag; print('OK')" 2>$null
if ($pygbagInstalled -ne "OK") {
    Write-Host "Installing Pygbag..." -ForegroundColor Yellow
    pip install --upgrade pygbag
} else {
    Write-Host "Pygbag is ready." -ForegroundColor Green
}

# Step 2: Ensure directories exist
Write-Host "`n[2/5] Preparing output directories..." -ForegroundColor Yellow
if (-not (Test-Path "dist")) { New-Item -ItemType Directory -Path "dist" | Out-Null }
if (-not (Test-Path "dist\web")) { New-Item -ItemType Directory -Path "dist\web" | Out-Null }

# Step 3: Build WebAssembly package via Pygbag
Write-Host "`n[3/5] Compiling WebAssembly package via Pygbag..." -ForegroundColor Yellow
python -m pygbag --build --template web/template.tmpl --icon Asteroid.png --app_name asteroids main.py
if ($LASTEXITCODE -ne 0) {
    Write-Error "Pygbag build failed with code $LASTEXITCODE"
}

# Step 4: Copy artifacts to dist\web
Write-Host "`n[4/5] Syncing artifacts to dist\web\..." -ForegroundColor Yellow
Copy-Item -Path "build\web\*" -Destination "dist\web\" -Recurse -Force
if (Test-Path "CNAME") {
    Copy-Item "CNAME" -Destination "dist\web\CNAME" -Force
}
Write-Host "Generated files in dist\web\:" -ForegroundColor Green
Get-ChildItem "dist\web" | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize

# Step 5: Create itch.io / static web deployment zip archive
Write-Host "`n[5/5] Packaging zip distribution for itch.io / static hosting..." -ForegroundColor Yellow
$zipPath = "dist\asteroids-3d-web.zip"
if (Test-Path $zipPath) { Remove-Item $zipPath -Force }
Compress-Archive -Path "dist\web\*" -DestinationPath $zipPath -Force
Write-Host "Web distribution archive created: $zipPath" -ForegroundColor Green

Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "  BUILD COMPLETE: dist\web\ (ready for GitHub Pages / itch.io)" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

if ($Serve) {
    Write-Host "`nStarting local test server on http://localhost:$Port ..." -ForegroundColor Cyan
    Write-Host "Press Ctrl+C to stop server." -ForegroundColor DarkGray
    python -m http.server --directory dist/web $Port
}

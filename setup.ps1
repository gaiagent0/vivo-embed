$Dir = "C:\AI\apps\vivo-embed"
Write-Host "=== vivo-embed setup ===" -ForegroundColor Cyan
Set-Location $Dir
$uv = @("$env:USERPROFILE\.local\bin\uv.exe","$env:USERPROFILE\.cargo\bin\uv.exe") | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $uv) { Write-Host "Telepitsd az uv-t: https://astral.sh/uv" -ForegroundColor Red; exit 1 }
& $uv venv --python 3.12 .venv --clear
& $uv pip install -r requirements.txt
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }
Write-Host "Kesz! Szerkeszd: notepad $Dir\.env" -ForegroundColor Green
Write-Host "Majd inditsd: .\start.ps1" -ForegroundColor Green

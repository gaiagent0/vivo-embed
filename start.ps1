$Dir = "C:\AI\apps\vivo-embed"
$env:PYTHONUTF8       = "1"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONPATH       = "$Dir\src"
$p = netstat -ano | Select-String ":7272\s" | Select-String "LISTENING"
if ($p) { Stop-Process -Id ([int](($p -split '\s+' | Select-Object -Last 1).Trim())) -Force -EA SilentlyContinue; Start-Sleep 2 }
if (Test-Path "$Dir\.env") {
    Get-Content "$Dir\.env" | ForEach-Object {
        if ($_ -match '^\s*([^#=][^=]*)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
        }
    }
}
if (-not $env:GOOGLE_API_KEY) { Write-Host "HIBA: GOOGLE_API_KEY nincs beallitva!" -ForegroundColor Red; exit 1 }
Write-Host "vivo-embed indul: http://localhost:7272" -ForegroundColor Cyan
Set-Location $Dir
& "$Dir\.venv\Scripts\python.exe" src\main.py

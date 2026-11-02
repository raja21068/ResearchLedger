# Start the ResearchLedger web app: API (FastAPI, uses your Claude Code login) + GUI (Next.js).
# Usage (PowerShell, from anywhere):  & D:\AutoResearch\ResearchLedger\start_web.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# Pick a Python that already has the backend packages; install them only if none does.
$candidates = @("python", "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe", "py")
$python = $null
foreach ($c in $candidates) {
    try {
        & $c -c "import fastapi, uvicorn, multipart, mammoth, docx" 2>$null
        if ($LASTEXITCODE -eq 0) { $python = $c; break }
    } catch { }
}
if (-not $python) {
    Write-Host "Installing backend packages into 'python'..."
    python -m pip install -r "$root\webapi\requirements.txt"
    $python = "python"
}

if (-not (Test-Path "$root\frontend\node_modules")) {
    Write-Host "Installing frontend packages..."
    Push-Location "$root\frontend"; npm install --no-audit --no-fund; Pop-Location
}

Write-Host "Starting API on http://127.0.0.1:8000 with $python"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; & '$python' -m uvicorn webapi.app.main:app --host 127.0.0.1 --port 8000"
Write-Host "Starting GUI on http://localhost:3000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev"
Start-Sleep -Seconds 6
Start-Process "http://localhost:3000"

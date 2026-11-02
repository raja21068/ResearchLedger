# Install the ResearchLedger console commands (/rl, /rl-status, /rl-worker) for Claude Code on THIS computer,
# so they work in a Claude Code session opened in any folder.
# Usage (PowerShell):  & .\install_console.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# The Python that runs the helpers: the first one that works.
$python = $null
foreach ($c in @("python", "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe", "py")) {
    try { $p = (& $c -c "import sys; print(sys.executable)" 2>$null); if ($LASTEXITCODE -eq 0 -and $p) { $python = $p.Trim(); break } } catch { }
}
if (-not $python) { throw "Python 3.10+ was not found. Install it from python.org, then run this again." }

$dest = Join-Path $HOME ".claude\commands"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
foreach ($name in @("rl.md", "rl-status.md", "rl-worker.md")) {
    $text = Get-Content -Raw -Encoding UTF8 (Join-Path $root ".claude\commands\$name")
    # Relative helper paths in the repository become absolute ones, so the commands work from any folder.
    $text = $text.Replace("python webapi/rl_cli.py", "$python $root\webapi\rl_cli.py")
    $text = $text.Replace("python webapi/bridge_cli.py", "$python $root\webapi\bridge_cli.py")
    $text = $text.Replace("& .\start_web.ps1", "& $root\start_web.ps1")
    $target = Join-Path $dest $name
    [System.IO.File]::WriteAllText($target, $text, (New-Object System.Text.UTF8Encoding $false))
    Write-Host "Installed /$($name -replace '\.md$','')  ->  $target"
}
Write-Host ""
Write-Host "Done. Open a NEW Claude Code session and type /rl"

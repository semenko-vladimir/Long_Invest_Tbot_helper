$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$PythonSource = "python"
$PyList = & py -0p 2>$null
if ($LASTEXITCODE -eq 0) {
    $Python312Line = $PyList | Where-Object { $_ -match "3\.12" } | Select-Object -First 1
    if ($Python312Line -and $Python312Line -match "([A-Za-z]:\\.*python\.exe)$") {
        $PythonSource = $Matches[1]
    }
}

Write-Host "Using Python: $PythonSource"

if (-not (Test-Path -LiteralPath "venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..."
    & $PythonSource -m venv venv
} else {
    Write-Host "Virtual environment already exists."
}

$Python = Join-Path $RepoRoot "venv\Scripts\python.exe"

Write-Host "Installing minimal investor v1 dependencies..."
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements-v1.txt

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
    Write-Host "Created .env from .env.example. Fill BOT_TOKEN, SANDBOX_TOKEN, and CHAT_ID before starting."
} else {
    Write-Host ".env already exists; leaving it unchanged."
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  .\venv\Scripts\Activate.ps1"
Write-Host "  python app/run.py"
Write-Host "  curl http://localhost:8000/"

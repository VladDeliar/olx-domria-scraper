# Dev-mode helper: opens 4 PowerShell windows for the four long-running services.
# Memurai (Redis) runs as a Windows service; no window needed for it.
# Stop everything by closing each window or Ctrl-C inside.

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Definition
$python = Join-Path $root "venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "venv not found at $python. Run 'uv sync' first." -ForegroundColor Red
    exit 1
}

function Start-Service-Window {
    param([string]$Title, [string]$Args)
    $cmd = @"
`$Host.UI.RawUI.WindowTitle = '$Title'
`$env:PYTHONIOENCODING = 'utf-8'
Set-Location '$root\webapp'
& '$python' $Args
"@
    Start-Process powershell.exe -ArgumentList "-NoExit", "-Command", $cmd
}

Start-Service-Window -Title "Django"        -Args "manage.py runserver"
Start-Service-Window -Title "Telegram bot"  -Args "manage.py run_bot"
Start-Service-Window -Title "Celery worker" -Args "-m celery -A config worker --pool=solo --loglevel=INFO"
Start-Service-Window -Title "Celery beat"   -Args "-m celery -A config beat --loglevel=INFO"

Write-Host "Spawned 4 service windows. URLs:" -ForegroundColor Green
Write-Host "  http://127.0.0.1:8000/            list"
Write-Host "  http://127.0.0.1:8000/dashboard/  dashboard"
Write-Host "  http://127.0.0.1:8000/admin/      admin"
Write-Host "  http://127.0.0.1:8000/api/listings/  REST API"

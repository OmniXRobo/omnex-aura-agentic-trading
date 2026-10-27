$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not $env:AURA_ADMIN_TOKEN -or $env:AURA_ADMIN_TOKEN.Length -lt 32) {
    throw "Configure AURA_ADMIN_TOKEN in the service environment first."
}
if (-not (Test-Path .venv)) { py -3.12 -m venv .venv; if ($LASTEXITCODE) { throw "venv failed" } }
& .\.venv\Scripts\python.exe -m pip install -r requirements.lock
if ($LASTEXITCODE) { throw "Dependency installation failed" }
& .\.venv\Scripts\python.exe -m pip install -e . --no-deps
if ($LASTEXITCODE) { throw "Installation failed" }
& .\.venv\Scripts\python.exe -m uvicorn aura.api:create_app --factory --host 127.0.0.1 --port 8080
exit $LASTEXITCODE

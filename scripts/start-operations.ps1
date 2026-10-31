param([string]$DataDir = (Join-Path (Split-Path $PSScriptRoot -Parent) 'data'))
$ErrorActionPreference = 'Stop'
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root
& (Join-Path $Root '.venv\Scripts\python.exe') -m aura.operations --data-dir $DataDir
exit $LASTEXITCODE

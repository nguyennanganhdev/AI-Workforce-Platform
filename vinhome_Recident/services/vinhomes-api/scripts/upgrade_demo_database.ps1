$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$projectRoot = Split-Path (Split-Path $serviceRoot -Parent) -Parent
$config = Join-Path $serviceRoot '.local-v3-faker/migration.env'
if (!(Test-Path -LiteralPath $config)) { throw 'Run setup_demo_database.ps1 first' }
if (!(Get-Command bun -ErrorAction SilentlyContinue)) { throw 'Bun is required for V3 migrations' }
$previousDatabaseUrl = $env:DATABASE_URL
try {
    $env:DATABASE_URL = (Get-Content -LiteralPath $config | Where-Object { $_.StartsWith('DATABASE_URL=') }) -replace '^DATABASE_URL=', ''
    & bun (Join-Path $projectRoot 'server/scripts/migrate.ts')
    if ($LASTEXITCODE -ne 0) { throw 'V3 migration failed' }
} finally { $env:DATABASE_URL = $previousDatabaseUrl }
$python = Join-Path $serviceRoot '.venv/Scripts/python.exe'
& $python (Join-Path $PSScriptRoot 'prepare_demo_database.py') upgrade
if ($LASTEXITCODE -ne 0) { throw 'V3 extension seed/grants failed' }
Write-Host 'V3 migration and additional faker fixtures ready; existing workflow state preserved.'

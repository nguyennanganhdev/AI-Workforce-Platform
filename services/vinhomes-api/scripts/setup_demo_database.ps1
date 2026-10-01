$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$projectRoot = Split-Path (Split-Path $serviceRoot -Parent) -Parent
$python = Join-Path $serviceRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { $python = 'python' }
& $python (Join-Path $PSScriptRoot 'prepare_demo_database.py') prepare
if ($LASTEXITCODE -ne 0) { throw 'Unable to prepare database configuration' }
docker compose -p vinhomes-faker-v3 -f (Join-Path $serviceRoot 'docker-compose.demo.yml') up -d --wait
if ($LASTEXITCODE -ne 0) { throw 'Docker database is unavailable; start Docker Linux engine and rerun this script' }
$migrationConfig = Get-Content (Join-Path $serviceRoot '.local-v3-faker/migration.env')
$previousDatabaseUrl = $env:DATABASE_URL
try {
    $env:DATABASE_URL = ($migrationConfig | Where-Object { $_.StartsWith('DATABASE_URL=') }) -replace '^DATABASE_URL=', ''
    bun (Join-Path $projectRoot 'server/scripts/migrate.ts')
    if ($LASTEXITCODE -ne 0) { throw 'V3 migrations failed' }
} finally {
    $env:DATABASE_URL = $previousDatabaseUrl
}
& $python (Join-Path $PSScriptRoot 'prepare_demo_database.py') seed
if ($LASTEXITCODE -ne 0) { throw 'V3 faker seed failed' }
Write-Host 'Database demo ready. Run scripts/start_demo.ps1 and open http://localhost:8000/docs'

$ErrorActionPreference = 'Stop'
$apiPath = Join-Path (Split-Path $PSScriptRoot -Parent) 'services/platform-api'
$localValues = @{}
Get-Content -LiteralPath (Join-Path $PSScriptRoot '.env') | ForEach-Object {
    if ($_ -match '^([^#=]+)=(.*)$') { $localValues[$matches[1]] = $matches[2] }
}
$env:VP_TEST_DATABASE_URL = 'postgresql+asyncpg://vp_platform:' + $localValues['VP_DB_PASSWORD'] + '@127.0.0.1:5588/vp_platform_test'
try {
    Push-Location $apiPath
    uv run pytest -q
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL tests failed' }
} finally {
    Pop-Location
    Remove-Item Env:VP_TEST_DATABASE_URL -ErrorAction SilentlyContinue
}

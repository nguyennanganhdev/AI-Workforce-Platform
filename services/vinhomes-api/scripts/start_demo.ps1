$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$env:PYTHONPATH = Join-Path $serviceRoot 'src'
$configFile = Join-Path $serviceRoot '.local-v3-faker/api.env'
if (!(Test-Path -LiteralPath $configFile)) { throw 'Run scripts/setup_demo_database.ps1 first to create the V3 faker database' }
# Optional: reception.env turns on the Reception agent (see connected.env.example for the keys).
$receptionFile = Join-Path $serviceRoot '.local-v3-faker/reception.env'
@($configFile, $receptionFile) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-Content -LiteralPath $_ } | ForEach-Object {
    if ($_ -and !$_.StartsWith('#')) {
        $setting = $_ -split '=', 2
        [Environment]::SetEnvironmentVariable($setting[0], $setting[1], 'Process')
    }
}
$env:VINHOMES_API_AUTH_URL = ''
$env:VINHOMES_API_DEV_USER_ID = ''
$env:VINHOMES_API_TENANT_KEY = ''
$python = Join-Path $serviceRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { $python = 'python' }
& $python -m vinhomes_api
exit $LASTEXITCODE

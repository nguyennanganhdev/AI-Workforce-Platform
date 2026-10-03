# Starts the technical tool host for Supervisor sessions on 127.0.0.1:8788 for the local demo,
# or with -Connected for the password-login deployment. Settings: technical-api.env in
# .local-v3-faker or .local-connected, written by scripts/setup_session_tools.py.
param([switch]$Connected)
$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$projectRoot = Split-Path (Split-Path $serviceRoot -Parent) -Parent
$local = if ($Connected) { '.local-connected' } else { '.local-v3-faker' }
$configFile = Join-Path $serviceRoot "$local/technical-api.env"
if (!(Test-Path -LiteralPath $configFile)) { throw "Run scripts/setup_session_tools.py first to create $local/technical-api.env" }
Get-Content -LiteralPath $configFile | ForEach-Object {
    if ($_ -and !$_.StartsWith('#')) {
        $setting = $_ -split '=', 2
        if ($setting[1] -and $setting[0].StartsWith('TECHNICAL_')) {
            [Environment]::SetEnvironmentVariable($setting[0], $setting[1], 'Process')
        }
    }
}
# Bun prefers DATABASE_URL over what the service passes; the service must use its own.
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Set-Location -LiteralPath (Join-Path $projectRoot 'server')
& bun src/technical-api/serve.ts
exit $LASTEXITCODE

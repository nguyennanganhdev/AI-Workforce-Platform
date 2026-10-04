# Starts the schedule service for management's agents on 127.0.0.1:8789, for the local
# password-login deployment. Settings: .local-connected/routines.env, written by scripts/setup_routines.py.
$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$projectRoot = Split-Path (Split-Path $serviceRoot -Parent) -Parent
$configFile = Join-Path $serviceRoot '.local-connected/routines.env'
if (!(Test-Path -LiteralPath $configFile)) { throw 'Run scripts/setup_routines.py first to create .local-connected/routines.env' }
Get-Content -LiteralPath $configFile | ForEach-Object {
    if ($_ -and !$_.StartsWith('#')) {
        $setting = $_ -split '=', 2
        if ($setting[1] -and $setting[0].StartsWith('ROUTINES_')) {
            [Environment]::SetEnvironmentVariable($setting[0], $setting[1], 'Process')
        }
    }
}
# Bun prefers DATABASE_URL over what the service passes; the service must use its own.
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Set-Location -LiteralPath (Join-Path $projectRoot 'server')
& bun src/room-routines/serve.ts
exit $LASTEXITCODE

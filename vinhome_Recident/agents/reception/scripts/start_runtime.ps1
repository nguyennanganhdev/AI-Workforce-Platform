# Starts the Reception runtime on 127.0.0.1:4202 with the settings in agents/reception/.env.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$configFile = Join-Path $root '.env'
if (!(Test-Path -LiteralPath $configFile)) { throw 'Copy .env.example to .env and fill in the Reception runtime settings first' }
Get-Content -LiteralPath $configFile | ForEach-Object {
    if ($_ -and !$_.StartsWith('#')) {
        $setting = $_ -split '=', 2
        [Environment]::SetEnvironmentVariable($setting[0], $setting[1], 'Process')
    }
}
$python = Join-Path $root '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { $python = 'python' }
Set-Location -LiteralPath $root
& $python -m uvicorn src.runtime.service:create_app --factory --host 127.0.0.1 --port 4202
exit $LASTEXITCODE

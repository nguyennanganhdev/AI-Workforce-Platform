# Starts the Supervisor for the Vinhomes business API on 127.0.0.1:4300 (src/vinhomes).
# Settings: agent-coordination/.env (COORDINATION_BACKEND_URL, COORDINATION_SERVICE_TOKEN, and
# for specialists COORDINATION_MODEL, COORDINATION_OPENBOT_URL, MANAGED_AGENT_TOKEN); the model
# key comes from agent-reception/.env.
# The demo and the password-login deployment are different databases, so each keeps its own
# state file: use -Connected when the backend was started with start_connected.ps1.
param([switch]$Connected)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$configFile = Join-Path $root '.env'
if (!(Test-Path -LiteralPath $configFile)) { throw 'Create agent-coordination/.env with COORDINATION_BACKEND_URL and COORDINATION_SERVICE_TOKEN first (see .env.example)' }
$keyFile = Join-Path (Split-Path $root -Parent) 'agent-reception/.env'
@($keyFile, $configFile) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-Content -LiteralPath $_ } | ForEach-Object {
    if ($_ -and !$_.StartsWith('#')) {
        $setting = $_ -split '=', 2
        if ($setting[1] -and ($setting[0].StartsWith('COORDINATION_') -or $setting[0] -in @('MANAGED_AGENT_TOKEN', 'OPENAI_API_KEY'))) {
            [Environment]::SetEnvironmentVariable($setting[0], $setting[1], 'Process')
        }
    }
}
$name = if ($Connected) { 'connected' } else { 'demo' }
$env:COORDINATION_STATE_PATH = Join-Path $root ".coordination-state/$name.sqlite3"
$env:PYTHONPATH = Join-Path $root 'src'
# The schema files are UTF-8; Windows would otherwise read them as cp1252.
$env:PYTHONUTF8 = '1'
$python = Join-Path $root '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Create agent-coordination/.venv with Python 3.12 and install requirements.lock first (see README.md)' }
Set-Location -LiteralPath $root
& $python -m vinhomes
exit $LASTEXITCODE

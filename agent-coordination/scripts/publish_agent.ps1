# Takes an agent definition through draft, evaluation and admin review (src/vinhomes/publish.py).
#   publish_agent.ps1 ..\docs\teams\quang\agent\technical-agent.json -Room management-room
#   publish_agent.ps1 ..\docs\teams\quang\agent\technical-agent.json -Room bql-sapphire -Connected -Approve
# Needs the backend and the OpenBot (start_openbot.ps1) running, and for an agent with tools the
# technical tool host (services/vinhomes-api/scripts/start_technical_tools.ps1). Without -Connected the backend's
# demo actors are used; with it, management signs in with the account in
# services/vinhomes-api/.local-connected/accounts.txt and -Approve uses initial-admin.txt.
# Neither password is printed.
param([Parameter(Mandatory)][string]$Definition, [Parameter(Mandatory)][string]$Room, [switch]$Connected, [switch]$Approve)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$project = Split-Path $root -Parent
Get-Content -LiteralPath (Join-Path $root '.env') | ForEach-Object {
    if ($_ -and !$_.StartsWith('#')) {
        $setting = $_ -split '=', 2
        if ($setting[1] -and ($setting[0].StartsWith('COORDINATION_') -or $setting[0] -eq 'MANAGED_AGENT_TOKEN')) {
            [Environment]::SetEnvironmentVariable($setting[0], $setting[1], 'Process')
        }
    }
}
# The technical tool host, when scripts/setup_session_tools.py has prepared it for this deployment
# (services/vinhomes-api/scripts/start_technical_tools.ps1 runs it on 8788).
$toolsFile = Join-Path (Split-Path $root -Parent) "services/vinhomes-api/$(if ($Connected) { '.local-connected' } else { '.local-v3-faker' })/technical-api.env"
if (Test-Path -LiteralPath $toolsFile) {
    $toolsToken = (Get-Content -LiteralPath $toolsFile | Where-Object { $_.StartsWith('TECHNICAL_TOOLS_SERVICE_TOKEN=') }) -replace '^TECHNICAL_TOOLS_SERVICE_TOKEN=', ''
    if ($toolsToken) {
        $env:COORDINATION_TOOLS_URL = 'http://127.0.0.1:8788/internal/technical/v1'
        $env:COORDINATION_TOOLS_TOKEN = $toolsToken
    }
}
$arguments = @('-m', 'vinhomes.publish', (Resolve-Path -LiteralPath $Definition).Path, '--room', $Room)
if ($Connected) {
    $local = Join-Path $project 'services/vinhomes-api/.local-connected'
    # accounts.txt: "management: <email> / <password>"; initial-admin.txt: "Login: ..." and "Password: ...".
    $management = (Get-Content -LiteralPath (Join-Path $local 'accounts.txt') | Where-Object { $_.StartsWith('management: ') } | Select-Object -First 1).Substring(12) -split ' / ', 2
    $env:PUBLISH_MANAGEMENT_EMAIL = $management[0]; $env:PUBLISH_MANAGEMENT_PASSWORD = $management[1]
    if ($Approve) {
        $admin = Get-Content -LiteralPath (Join-Path $local 'initial-admin.txt')
        $env:PUBLISH_ADMIN_EMAIL = ($admin | Where-Object { $_.StartsWith('Login: ') }).Substring(7)
        $env:PUBLISH_ADMIN_PASSWORD = ($admin | Where-Object { $_.StartsWith('Password: ') }).Substring(10)
    }
} else { $arguments += '--demo' }
if ($Approve) { $arguments += '--approve' }
$env:PYTHONPATH = Join-Path $root 'src'
$env:PYTHONUTF8 = '1'
Set-Location -LiteralPath $root
& (Join-Path $root '.venv/Scripts/python.exe') @arguments
exit $LASTEXITCODE

param([string]$ConfigFile)
$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
if (!$ConfigFile) { $ConfigFile = Join-Path $serviceRoot '.env.connected' }
if (!(Test-Path -LiteralPath $ConfigFile)) { throw "Missing $ConfigFile. Configure a real database, tenant and authentication endpoint. This launcher never seeds demo data." }
$settings = @{}
# Optional: reception.env turns on the Reception agent. The local Reception runtime is shared
# with the demo, so its settings are read from there unless this deployment has its own.
$receptionFile = @('.local-connected/reception.env', '.local-v3-faker/reception.env') |
    ForEach-Object { Join-Path $serviceRoot $_ } | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
@($receptionFile, $ConfigFile) | Where-Object { $_ } | ForEach-Object { Get-Content -LiteralPath $_ } | ForEach-Object {
    if ($_ -and !$_.StartsWith('#') -and $_.Contains('=')) {
        $pair = $_ -split '=', 2
        $settings[$pair[0].Trim()] = $pair[1].Trim()
    }
}
foreach ($required in @('VINHOMES_API_DATABASE_URL', 'VINHOMES_API_TENANT_ID')) {
    if (!$settings[$required]) { throw "Missing $required in connected configuration." }
}
if ($settings['VINHOMES_API_DEMO_MODE'] -eq '1' -or $settings['VINHOMES_API_DEV_USER_ID']) { throw 'Connected mode requires real sessions; demo and fixed development identities are forbidden.' }
if ($settings['VINHOMES_API_TENANT_ID'] -eq '11111111-1111-5111-a111-111111111111') { throw 'The seeded demo tenant cannot be used as the real deployment.' }
if ($settings['VINHOMES_API_PASSWORD_AUTH'] -ne '1') {
$authUrl = [Uri]$settings['VINHOMES_API_AUTH_URL']
if (!$authUrl.IsAbsoluteUri -or ($authUrl.Scheme -ne 'https' -and !($authUrl.Scheme -eq 'http' -and $authUrl.IsLoopback))) { throw 'Authentication requires HTTPS, or HTTP on loopback.' }
# A public session endpoint must not silently admit anonymous callers (single-user mode).
try {
    $session = Invoke-RestMethod -Uri $authUrl.AbsoluteUri -TimeoutSec 5
    if ($session.user.id) { throw 'Authentication endpoint granted an identity without a session. Disable single-user mode.' }
} catch {
    if (!$_.Exception.Response -or [int]$_.Exception.Response.StatusCode -notin @(401,403)) { throw }
}
}
foreach ($key in $settings.Keys) { [Environment]::SetEnvironmentVariable($key,$settings[$key],'Process') }
$env:VINHOMES_API_DEMO_MODE = '0'
$env:VINHOMES_API_DEV_USER_ID = ''
$env:VINHOMES_API_TENANT_KEY = ''
$env:PYTHONPATH = Join-Path $serviceRoot 'src'
$python = Join-Path $serviceRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $python)) { throw 'Install the API virtual environment in services/vinhomes-api/.venv first.' }
& $python -m vinhomes_api
exit $LASTEXITCODE

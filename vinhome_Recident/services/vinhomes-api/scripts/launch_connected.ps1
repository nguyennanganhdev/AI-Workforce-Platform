$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$projectRoot = Split-Path (Split-Path $serviceRoot -Parent) -Parent
$configFile = Join-Path $serviceRoot '.env.connected'
if (!(Test-Path -LiteralPath $configFile)) { throw 'Missing services/vinhomes-api/.env.connected. See connected.env.example. No demo fallback is allowed.' }
$logRoot = Join-Path $serviceRoot '.local-connected'
New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$health = $null
try { $health = Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 3 } catch {}
if ($health -and ($health.service -ne 'vinhomes-api' -or $health.dataMode -ne 'database' -or $health.authMode -notin @('session','password'))) { throw 'Port 8000 is occupied by a demo or another service. Stop that process first.' }
if (!$health) {
    if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 8000 is occupied.' }
    $startScript = Join-Path $PSScriptRoot 'start_connected.ps1'
    Start-Process powershell.exe -ArgumentList ('-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $startScript) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot 'api.stdout.log') -RedirectStandardError (Join-Path $logRoot 'api.stderr.log') | Out-Null
}
$ready = $false
for ($attempt=0; $attempt -lt 20; $attempt++) {
    try { $ready = (Invoke-RestMethod 'http://127.0.0.1:8000/ready' -TimeoutSec 2).status -eq 'ready' } catch {}
    if ($ready) { break }
    Start-Sleep -Seconds 1
}
if (!$ready) { throw 'Backend is not ready. See services/vinhomes-api/.local-connected/api.stderr.log.' }
foreach ($frontend in @(@{Port=3011;Script='dev:resident';Name='resident'},@{Port=3020;Script='dev:operations';Name='operations'})) {
    if (!(Get-NetTCPConnection -LocalPort $frontend.Port -State Listen -ErrorAction SilentlyContinue)) {
        # Script names are constants defined above; no config values are interpolated into shell code.
        $command = '$env:VITE_ALLOW_DEMO_BACKEND="false"; $env:VITE_ENABLE_UI_PREVIEW="false"; npm run ' + $frontend.Script
        Start-Process powershell.exe -ArgumentList @('-NoProfile','-Command',$command) -WorkingDirectory $projectRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $logRoot ($frontend.Name+'.stdout.log')) -RedirectStandardError (Join-Path $logRoot ($frontend.Name+'.stderr.log')) | Out-Null
    }
}
Write-Host 'Resident: http://127.0.0.1:3011/'
Write-Host 'Operations: http://127.0.0.1:3020/operations'
Write-Host 'Sign in with a real account provisioned for the configured tenant.'

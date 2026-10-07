$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$runtimeRoot = Join-Path $projectRoot '.codex-artifacts/portable/runtime'
$stateRoot = Join-Path $projectRoot '.codex-artifacts/portable'
$env:PATH = "$runtimeRoot\Library\bin;$runtimeRoot;$env:USERPROFILE\.bun\bin;$env:PATH"
$env:PYTHONUTF8 = '1'
$python = Join-Path $runtimeRoot 'python.exe'
$bun = (Get-Command bun -ErrorAction Stop).Source
if (!(Test-Path $python)) { throw 'Portable runtime is missing. See docs/local-portable.md.' }
function Import-LocalEnv([string]$Path) {
    if (!(Test-Path $Path)) { throw "Missing local configuration: $Path" }
    foreach ($line in Get-Content -LiteralPath $Path) {
        if ($line -and !$line.StartsWith('#') -and $line.Contains('=')) {
            $pair = $line -split '=',2
            [Environment]::SetEnvironmentVariable($pair[0],$pair[1],'Process')
        }
    }
}
function Test-LocalPort([int]$Port) {
    $client = New-Object Net.Sockets.TcpClient
    try { $client.Connect('127.0.0.1',$Port); return $true } catch { return $false } finally { $client.Dispose() }
}
function Start-LocalService([string]$Name,[int]$Port,[string]$File,[string]$Arguments,[string]$Directory) {
    if (Test-LocalPort $Port) { Write-Host "$Name already listening on $Port (left running)"; return }
    $process = Start-Process -FilePath $File -ArgumentList $Arguments -WorkingDirectory $Directory -WindowStyle Hidden `
        -RedirectStandardOutput "$stateRoot/$Name.out.log" -RedirectStandardError "$stateRoot/$Name.err.log" -PassThru
    @{ id=$process.Id; started=$process.StartTime.ToUniversalTime().ToString('o') } | ConvertTo-Json | Set-Content "$stateRoot/$Name.process.json"
    for ($attempt=0; $attempt -lt 30; $attempt++) {
        if (Test-LocalPort $Port) { Write-Host "$Name ready at http://127.0.0.1:$Port"; return }
        Start-Sleep -Milliseconds 500
        $process.Refresh()
        if ($process.HasExited) { throw "$Name exited. See $stateRoot/$Name.err.log" }
    }
    throw "$Name did not open port $Port. See $stateRoot/$Name.err.log"
}
Start-LocalService 'postgres' 5544 "$runtimeRoot/Library/bin/postgres.exe" '-D services/vinhomes-api/.local-postgres/data -h 127.0.0.1 -p 5544' $projectRoot
Import-LocalEnv "$projectRoot/services/vinhomes-api/.env.connected"
$env:PYTHONPATH = "$projectRoot/services/vinhomes-api/src"
Start-LocalService 'api' 8000 $python '-m vinhomes_api' $projectRoot
Import-LocalEnv "$projectRoot/.env"
Start-LocalService 'platform' 3001 $bun '--env-file=../.env src/business-connections.ts' "$projectRoot/server"
Push-Location $projectRoot
try { & $bun scripts/generate-app-config.ts; if ($LASTEXITCODE -ne 0) { throw 'App configuration generation failed' } } finally { Pop-Location }
$env:VINHOMES_SURFACE = 'operations'
Start-LocalService 'operations' 3020 $bun '--bun scripts/vite.mjs --port 3020 --host 127.0.0.1' "$projectRoot/app"
$env:VINHOMES_SURFACE = 'field'
Start-LocalService 'field' 3023 $bun '--bun scripts/vite.mjs --port 3023 --host 127.0.0.1' "$projectRoot/app"
$env:VINHOMES_SURFACE = 'resident'
Start-LocalService 'resident' 3011 $bun '--bun node_modules/vite/bin/vite.js --host 127.0.0.1 --port 3011 --strictPort' "$projectRoot/resident-app"
Write-Host 'Resident: http://127.0.0.1:3011'
Write-Host 'Management/admin: http://127.0.0.1:3020/operations/login'
Write-Host 'Field staff: http://127.0.0.1:3023/operations/login'
Write-Host 'API docs: http://127.0.0.1:8000/docs'
Write-Host 'AI agents need separate provider credentials; this starts the local business application.'

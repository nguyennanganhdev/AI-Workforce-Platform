$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
$stateRoot = Join-Path $projectRoot '.codex-artifacts/portable'
$runtimeRoot = Join-Path $stateRoot 'runtime'
$env:PATH = "$runtimeRoot\Library\bin;$runtimeRoot;$env:PATH"
# Only stop processes created by our launcher, and protect against recycled process IDs.
foreach ($name in @('resident','field','operations','platform','api')) {
    $recordPath = Join-Path $stateRoot "$name.process.json"
    if (!(Test-Path -LiteralPath $recordPath)) { continue }
    $record = Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json
    $process = Get-Process -Id $record.id -ErrorAction SilentlyContinue
    if ($process -and $process.StartTime.ToUniversalTime().ToString('o') -eq $record.started) {
        Stop-Process -Id $process.Id
        Write-Host "Stopped $name"
    }
    Remove-Item -LiteralPath $recordPath
}
$databaseDirectory = Join-Path $projectRoot 'services/vinhomes-api/.local-postgres/data'
if (Test-Path -LiteralPath "$databaseDirectory/postmaster.pid") {
    & "$runtimeRoot/Library/bin/pg_ctl.exe" -D $databaseDirectory -m fast -w stop
    if ($LASTEXITCODE -ne 0) { throw 'PostgreSQL did not stop cleanly; inspect its log.' }
}
Write-Host 'Local services stopped. Database and uploaded files preserved.'

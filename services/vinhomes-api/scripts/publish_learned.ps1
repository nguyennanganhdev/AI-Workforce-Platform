# Exports approved learned answers into the knowledge folder and publishes it (local demo).
# Each round also proposes emergency safety guidance from the folder for management to approve.
# Once:        scripts/publish_learned.ps1 -DataDir <Data-Vinhome> [-Site ocean-park-1] [-User local-v3-management]
# Keep going:  add -EveryMinutes 5 and leave it running next to the demo; unchanged files cost nothing.
param([Parameter(Mandatory = $true)][string]$DataDir, [string]$Site = 'ocean-park-1', [string]$User = 'local-v3-management',
      [int]$EveryMinutes = 0)
$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$projectRoot = Split-Path (Split-Path $serviceRoot -Parent) -Parent
$owner = (Get-Content -LiteralPath (Join-Path $serviceRoot '.local-v3-faker/migration.env') | Where-Object { $_.StartsWith('DATABASE_URL=') }) -replace '^DATABASE_URL=', ''
$key = (Get-Content -LiteralPath (Join-Path $projectRoot 'agent-reception/.env') | Where-Object { $_.StartsWith('OPENAI_API_KEY=') }) -replace '^OPENAI_API_KEY=', ''
$env:KNOWLEDGE_ADMIN_DATABASE_URL = $owner
$env:OPENAI_API_KEY = $key
Set-Location -LiteralPath (Join-Path $projectRoot 'server')
do {
    $env:DATABASE_URL = $owner
    $python = Join-Path $serviceRoot '.venv/Scripts/python.exe'
    & $python (Join-Path $PSScriptRoot 'propose_emergency_guidance.py') $DataDir
    $code = $LASTEXITCODE
    if ($code -eq 0) {
        & $python (Join-Path $PSScriptRoot 'export_learned_knowledge.py') $DataDir
        $code = $LASTEXITCODE
    }
    # Bun prefers DATABASE_URL over what the publisher passes; it must use its own setting.
    Remove-Item Env:DATABASE_URL
    if ($code -eq 0) {
        & bun src/knowledge/publish.ts $DataDir --site $Site --user $User
        $code = $LASTEXITCODE
    }
    if ($EveryMinutes -gt 0) {
        # A failed round is retried at the next one; the answers stay approved in the database.
        Write-Host "$(Get-Date -Format 'HH:mm:ss') round finished with exit code $code; next in $EveryMinutes minutes"
        Start-Sleep -Seconds ($EveryMinutes * 60)
    }
} while ($EveryMinutes -gt 0)
if ($code -ne 0) { throw "Export or publish failed with exit code $code" }

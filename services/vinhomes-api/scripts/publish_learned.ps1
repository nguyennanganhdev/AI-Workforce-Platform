# Exports approved learned answers into the knowledge folder and publishes it (local demo).
# Run on a schedule or after approvals:  scripts/publish_learned.ps1 -DataDir <Data-Vinhome> [-Site ocean-park-1] [-User local-v3-management]
param([Parameter(Mandatory = $true)][string]$DataDir, [string]$Site = 'ocean-park-1', [string]$User = 'local-v3-management')
$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$projectRoot = Split-Path (Split-Path $serviceRoot -Parent) -Parent
$owner = (Get-Content -LiteralPath (Join-Path $serviceRoot '.local-v3-faker/migration.env') | Where-Object { $_.StartsWith('DATABASE_URL=') }) -replace '^DATABASE_URL=', ''
$key = (Get-Content -LiteralPath (Join-Path $projectRoot 'agent-reception/.env') | Where-Object { $_.StartsWith('OPENAI_API_KEY=') }) -replace '^OPENAI_API_KEY=', ''
$env:DATABASE_URL = $owner
& (Join-Path $serviceRoot '.venv/Scripts/python.exe') (Join-Path $PSScriptRoot 'export_learned_knowledge.py') $DataDir
if ($LASTEXITCODE -ne 0) { throw 'Export failed' }
# Bun prefers DATABASE_URL over what the publisher passes; it must use its own setting.
Remove-Item Env:DATABASE_URL
$env:KNOWLEDGE_ADMIN_DATABASE_URL = $owner
$env:OPENAI_API_KEY = $key
Set-Location -LiteralPath (Join-Path $projectRoot 'server')
& bun src/knowledge/publish.ts $DataDir --site $Site --user $User
exit $LASTEXITCODE

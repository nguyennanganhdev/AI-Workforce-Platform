# Starts the knowledge search service on 127.0.0.1:8787 for the local demo, or with -Connected
# for the password-login deployment. Settings: knowledge.env in .local-v3-faker or
# .local-connected; the embedding key comes from agent-reception/.env (OPENAI_API_KEY), or from
# KNOWLEDGE_EMBEDDING_API_KEY / KNOWLEDGE_EMBEDDING_BASE_URL when the chat model uses another vendor.
param([switch]$Connected)
$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$projectRoot = Split-Path (Split-Path $serviceRoot -Parent) -Parent
$local = if ($Connected) { '.local-connected' } else { '.local-v3-faker' }
$configFile = Join-Path $serviceRoot "$local/knowledge.env"
if (!(Test-Path -LiteralPath $configFile)) { throw "Publish the knowledge first (server/src/knowledge/publish.ts) and create $local/knowledge.env" }
$keyFile = Join-Path $projectRoot 'agent-reception/.env'
@($keyFile, $configFile) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-Content -LiteralPath $_ } | ForEach-Object {
    if ($_ -and !$_.StartsWith('#')) {
        $setting = $_ -split '=', 2
        if ($setting[1] -and ($setting[0] -like 'KNOWLEDGE_*' -or $setting[0] -in @('RECEPTION_API_URL', 'OPENAI_API_KEY', 'OPENAI_BASE_URL'))) {
            [Environment]::SetEnvironmentVariable($setting[0], $setting[1], 'Process')
        }
    }
}
# Bun prefers DATABASE_URL over what the service passes; the service must use its own.
Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue
Set-Location -LiteralPath (Join-Path $projectRoot 'server')
& bun src/knowledge/serve.ts
exit $LASTEXITCODE

# Writes deploy/deployment.env from deployment.env.example with fresh random secrets. Never replaces an
# existing file: its secrets are the ones the database and the bucket were created with.
$ErrorActionPreference = 'Stop'
$target = Join-Path $PSScriptRoot 'deployment.env'
if (Test-Path $target) {
    [Console]::Error.WriteLine('deploy/deployment.env already exists: not replaced.')
    exit 1
}
$random = [System.Security.Cryptography.RandomNumberGenerator]::Create()
function Hex([int]$count) {
    $bytes = New-Object byte[] $count
    $random.GetBytes($bytes)
    return -join ($bytes | ForEach-Object { $_.ToString('x2') })
}
$long = 'POSTGRES_PASSWORD=', 'API_DB_PASSWORD=', 'MINIO_ROOT_PASSWORD=', 'S3_SECRET_KEY=', 'RESIDENT_SIGNING_KEY=', 'RECEPTION_DELEGATION_KEY=', 'RECEPTION_SERVICE_TOKEN=', 'VINHOMES_API_PLATFORM_MCP_TOKEN=', 'VINHOMES_API_CONFIG_ENCRYPTION_KEY='
$lines = [IO.File]::ReadAllText((Join-Path $PSScriptRoot 'deployment.env.example')) -split "`r?`n" | ForEach-Object {
    if ($long -contains $_) { $_ + (Hex 32) } elseif ($_ -eq 'DEMO_PASSWORD=') { $_ + (Hex 8) } else { $_ }
}
# No BOM and plain line feeds: the file is read by docker compose.
[IO.File]::WriteAllText($target, ($lines -join "`n"), (New-Object System.Text.UTF8Encoding $false))
Write-Output 'Wrote deploy/deployment.env. Paste OPENAI_API_KEY into it, then:'
Write-Output '  docker compose --env-file deploy/deployment.env -f deploy/compose.yml up -d --build'

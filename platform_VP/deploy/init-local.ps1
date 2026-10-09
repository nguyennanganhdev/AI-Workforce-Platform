$ErrorActionPreference = 'Stop'
$platformRoot = Split-Path $PSScriptRoot -Parent
$envPath = Join-Path $PSScriptRoot '.env'
if (Test-Path -LiteralPath $envPath) { throw 'deploy/.env already exists; preserve encryption key and credentials.' }
function New-RandomToken([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($buffer) } finally { $generator.Dispose() }
    return [Convert]::ToBase64String($buffer).Replace('+','-').Replace('/','_').TrimEnd('=')
}
$fernetKey = (New-RandomToken 32) + '='
$databasePassword = New-RandomToken 24
$adminPassword = New-RandomToken 24
$lines = @(
    "VP_DB_PASSWORD=$databasePassword", "VP_ENCRYPTION_KEY=$fernetKey",
    'VP_BOOTSTRAP_EMAIL=admin@platform.local', "VP_BOOTSTRAP_PASSWORD=$adminPassword",
    'VP_COOKIE_SECURE=false', 'VP_TRUSTED_ORIGINS=http://localhost:3080,http://127.0.0.1:3080',
    'VP_WORKERS=8', 'VP_MAX_SESSIONS=20', 'VP_MONTHLY_BUDGET_MICROS=100000000',
    'VP_SESSION_BUDGET_MICROS=500000', 'VP_JEV_ENABLED=false', 'VP_ALLOW_PRIVATE_ENDPOINTS=false'
)
[System.IO.File]::WriteAllLines($envPath, $lines, [System.Text.UTF8Encoding]::new($false))
$accountDir = Join-Path $platformRoot '.local'
New-Item -ItemType Directory -Path $accountDir -Force | Out-Null
[System.IO.File]::WriteAllLines((Join-Path $accountDir 'accounts.txt'), @('URL: http://localhost:3080','Email: admin@platform.local',"Password: $adminPassword"), [System.Text.UTF8Encoding]::new($false))
Write-Output 'Created ignored deploy/.env and .local/accounts.txt. No credential values printed.'

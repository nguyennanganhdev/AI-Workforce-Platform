param([string]$EnvironmentFile = (Join-Path $PSScriptRoot 'deployment.env'))
$ErrorActionPreference = 'Stop'
$composeArguments = @('compose', '--env-file', $EnvironmentFile, '-f', (Join-Path $PSScriptRoot 'compose.yml'))
$writers = @('api','reception','coordination','openbot','knowledge','technical-tools','routines','factory','platform','operations','resident')
& docker @composeArguments --profile maintenance build backup
if ($LASTEXITCODE -ne 0) { throw 'Backup image build failed' }
try {
    & docker @composeArguments stop -t 30 @writers
    if ($LASTEXITCODE -ne 0) { throw 'Could not stop application writers' }
    & docker @composeArguments --profile maintenance run --rm backup backup
    if ($LASTEXITCODE -ne 0) { throw 'Backup failed' }
    & docker @composeArguments --profile maintenance run --rm backup restore-verify
    if ($LASTEXITCODE -ne 0) { throw 'Restore verification failed' }
} finally {
    & docker @composeArguments up -d @writers
    if ($LASTEXITCODE -ne 0) { throw 'Application restart failed; inspect compose status' }
}

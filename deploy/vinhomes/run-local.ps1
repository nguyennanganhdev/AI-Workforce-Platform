param([string]$EnvironmentFile = (Join-Path $PSScriptRoot 'deployment.env'))
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $EnvironmentFile)) { throw 'Create deployment.env using deployment.env.example and your database/provider credentials.' }
$composeArguments = @('compose', '--env-file', $EnvironmentFile, '-f', (Join-Path $PSScriptRoot 'compose.yml'))
function Invoke-Compose([string[]]$Arguments) {
    & docker @composeArguments @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Compose failed: ' + ($Arguments -join ' ')) }
}
Invoke-Compose -Arguments @('build')
Invoke-Compose -Arguments @('--profile','upgrade','run','--rm','upgrade')
Invoke-Compose -Arguments @('up','-d','minio')
Invoke-Compose -Arguments @('--profile','upgrade','run','--rm','storage')
Invoke-Compose -Arguments @('--profile','upgrade','run','--rm','catalogue')
Invoke-Compose -Arguments @('up','-d')
Invoke-Compose -Arguments @('--profile','upgrade','run','--rm','report-bootstrap')
Invoke-Compose -Arguments @('ps')

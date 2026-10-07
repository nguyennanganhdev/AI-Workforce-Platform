param([string]$EnvironmentFile = (Join-Path $PSScriptRoot 'deployment.env'))
$ErrorActionPreference = 'Stop'

$dockerCommand = Get-Command docker -ErrorAction SilentlyContinue
$dockerExecutable = if ($dockerCommand) { $dockerCommand.Source } else { Join-Path $env:ProgramFiles 'Docker\Docker\resources\bin\docker.exe' }
if (!(Test-Path -LiteralPath $dockerExecutable)) { throw 'Docker CLI is not installed.' }
if (!(Test-Path -LiteralPath $EnvironmentFile)) { throw 'Existing deployment.env is required.' }
if (!(Test-Path -LiteralPath (Join-Path $PSScriptRoot '../../services/vinhomes-api/.local-v3-faker/postgres.env'))) {
    throw 'Existing PostgreSQL environment file is required.'
}

# Resume existing containers and the preserved PostgreSQL volume.
# Do not rebuild images, initialize databases, or rerun migrations/seeds.
$composeArguments = @('compose', '--env-file', $EnvironmentFile,
    '-f', (Join-Path $PSScriptRoot 'compose.yml'),
    '-f', (Join-Path $PSScriptRoot 'compose.postgres.local.yml'))
function Invoke-LocalCompose([string[]]$Arguments) {
    & $dockerExecutable @composeArguments @Arguments
    if ($LASTEXITCODE -ne 0) { throw ('Compose failed: ' + ($Arguments -join ' ')) }
}

Invoke-LocalCompose -Arguments @('config', '--quiet')
Invoke-LocalCompose -Arguments @('up', '-d', '--no-deps', '--wait', '--wait-timeout', '90', 'postgres')
Invoke-LocalCompose -Arguments @('start', '--wait', '--wait-timeout', '120')
Invoke-LocalCompose -Arguments @('ps')

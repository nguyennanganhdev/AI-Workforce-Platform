param([string]$ConfigFile = "$PSScriptRoot/../services/vinhomes-api/.local-connected/factory.env")
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $ConfigFile)) { throw 'Configure the ignored factory.env first; see agent-factory/.env.example.' }
Get-Content -LiteralPath $ConfigFile | ForEach-Object {
    if ($_ -and !$_.StartsWith('#') -and $_.Contains('=')) {
        $setting = $_ -split '=', 2
        if ($setting[0].StartsWith('FACTORY_')) { [Environment]::SetEnvironmentVariable($setting[0], $setting[1], 'Process') }
    }
}
Set-Location -LiteralPath $PSScriptRoot
& bun src/server.ts
exit $LASTEXITCODE

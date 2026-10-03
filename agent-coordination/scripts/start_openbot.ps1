# Starts the OpenBot (agent-bot) the Supervisor's specialists run on, on 127.0.0.1:4200.
# The Bot keeps no agent of its own: each turn the Supervisor sends it the published
# instructions of the agent it speaks for. Settings: MANAGED_AGENT_TOKEN and the model from
# agent-coordination/.env; the model key from agent-reception/.env.
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$project = Split-Path $root -Parent
$settings = @{}
@((Join-Path $project 'agent-reception/.env'), (Join-Path $root '.env')) | Where-Object { Test-Path -LiteralPath $_ } | ForEach-Object { Get-Content -LiteralPath $_ } | ForEach-Object {
    if ($_ -and !$_.StartsWith('#')) {
        $setting = $_ -split '=', 2
        if ($setting[1]) { $settings[$setting[0]] = $setting[1] }
    }
}
if (!$settings['MANAGED_AGENT_TOKEN']) { throw 'Set MANAGED_AGENT_TOKEN in agent-coordination/.env first (see .env.example)' }
$env:MANAGED_AGENT_TOKEN = $settings['MANAGED_AGENT_TOKEN']
$env:OPENAI_API_KEY = $settings['OPENAI_API_KEY']
if ($settings['OPENAI_BASE_URL']) { $env:OPENAI_BASE_URL = $settings['OPENAI_BASE_URL'] }
$env:BOT_MODEL = if ($settings['COORDINATION_OPENBOT_MODEL']) { $settings['COORDINATION_OPENBOT_MODEL'] } else { $settings['COORDINATION_MODEL'] }
$env:PORT = '4200'
Set-Location -LiteralPath (Join-Path $project 'agent-bot')
& bun src/index.ts
exit $LASTEXITCODE

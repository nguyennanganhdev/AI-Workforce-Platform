# Starts the OpenBot (agent-bot) the Supervisor's specialists run on, on 127.0.0.1:4200.
# The Bot keeps no agent of its own: each turn the Supervisor sends it the published
# instructions of the agent it speaks for. Settings: MANAGED_AGENT_TOKEN and the model from
# agent-coordination/.env; the model key from agent-reception/.env. The specialists may use
# another vendor than the planner: COORDINATION_OPENBOT_MODEL_PROVIDER (openai, google, deepseek,
# groq, anthropic or custom), COORDINATION_OPENBOT_MODEL_API_KEY and COORDINATION_OPENBOT_MODEL_BASE_URL.
# OPENAI_API_KEY / OPENAI_BASE_URL are only used for OpenAI (same rule as src/vinhomes/models.py).
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
$bases = @{ openai = ''; google = 'https://generativelanguage.googleapis.com/v1beta/openai'; deepseek = 'https://api.deepseek.com'
            groq = 'https://api.groq.com/openai/v1'; anthropic = 'https://api.anthropic.com/v1'; custom = '' }
$provider = if ($settings['COORDINATION_OPENBOT_MODEL_PROVIDER']) { $settings['COORDINATION_OPENBOT_MODEL_PROVIDER'].ToLower() } else { 'openai' }
if (!$bases.ContainsKey($provider)) { throw "COORDINATION_OPENBOT_MODEL_PROVIDER must be one of: $($bases.Keys -join ', ')" }
$shared = $provider -eq 'openai'
$key = if ($settings['COORDINATION_OPENBOT_MODEL_API_KEY']) { $settings['COORDINATION_OPENBOT_MODEL_API_KEY'] } elseif ($shared) { $settings['OPENAI_API_KEY'] } else { '' }
$base = if ($settings['COORDINATION_OPENBOT_MODEL_BASE_URL']) { $settings['COORDINATION_OPENBOT_MODEL_BASE_URL'] } elseif ($shared) { $settings['OPENAI_BASE_URL'] } else { $bases[$provider] }
if ($provider -eq 'custom' -and !$base) { throw 'COORDINATION_OPENBOT_MODEL_BASE_URL is required with the custom provider' }
if (!$key -and !$base) { throw 'The specialists have no model key: set COORDINATION_OPENBOT_MODEL_API_KEY, or OPENAI_API_KEY for OpenAI' }
$env:OPENAI_API_KEY = $key
if ($base) { $env:OPENAI_BASE_URL = $base } else { Remove-Item Env:OPENAI_BASE_URL -ErrorAction SilentlyContinue }
$env:BOT_MODEL = if ($settings['COORDINATION_OPENBOT_MODEL']) { $settings['COORDINATION_OPENBOT_MODEL'] } else { $settings['COORDINATION_MODEL'] }
$env:PORT = '4200'
Set-Location -LiteralPath (Join-Path $project 'agent-bot')
& bun src/index.ts
exit $LASTEXITCODE

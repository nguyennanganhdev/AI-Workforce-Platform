$ErrorActionPreference = 'Stop'
$serviceRoot = Split-Path $PSScriptRoot -Parent
$projectRoot = Split-Path (Split-Path $serviceRoot -Parent) -Parent
$runtimeRoot = Join-Path $serviceRoot '.local-v3-faker'
$demoUrl = 'http://localhost:8000/demo/ui'
Set-Location -LiteralPath $projectRoot

function Get-ApiHealth {
    try { return Invoke-RestMethod -Uri 'http://127.0.0.1:8000/health' -TimeoutSec 2 }
    catch { return $null }
}

function Assert-DemoIdentity {
    $health = Get-ApiHealth
    if ($null -ne $health -and ($health.service -ne 'vinhomes-api' -or $health.schema -ne 'v3' -or $health.dataMode -ne 'faker-database')) {
        throw 'Port 8000 is running another API or a non-demo environment. Stop that service before launching the demo.'
    }
}

function Get-DockerReady {
    # Bound each probe because Docker CLI can stall while its engine boots.
    $probe = New-Object System.Diagnostics.Process
    $probe.StartInfo.FileName = $docker.Source
    $probe.StartInfo.Arguments = 'info --format "{{.ServerVersion}}"'
    $probe.StartInfo.UseShellExecute = $false
    $probe.StartInfo.CreateNoWindow = $true
    $probe.StartInfo.RedirectStandardOutput = $true
    $probe.StartInfo.RedirectStandardError = $true
    try {
        $null = $probe.Start()
        if (!$probe.WaitForExit(5000)) {
            $probe.Kill()
            return $false
        }
        return $probe.ExitCode -eq 0
    } finally { $probe.Dispose() }
}

try {
    Assert-DemoIdentity
    Write-Host '[1/4] Starting Docker...'
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (!$docker) { throw 'Docker CLI is missing. Install Docker Desktop with the Linux engine first.' }
    $dockerReady = $false
    $dockerReady = Get-DockerReady
    if (!$dockerReady) {
        $desktopPaths = @(
            (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe'),
            (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe')
        )
        $desktop = $desktopPaths | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
        if (!$desktop) { throw 'Docker Desktop was not found. Start the Docker Linux engine manually.' }
        Start-Process -FilePath $desktop -WindowStyle Hidden
        $deadline = (Get-Date).AddSeconds(120)
        do {
            Start-Sleep -Seconds 3
            $dockerReady = Get-DockerReady
        } until ($dockerReady -or (Get-Date) -gt $deadline)
        if (!$dockerReady) { throw 'Docker did not become ready within 120 seconds. Check Docker Desktop and WSL, then reopen services/CHAY_DEMO_API.cmd.' }
    }

    Write-Host '[2/4] Starting PostgreSQL V3...'
    $configFiles = @('api.env', 'postgres.env', 'migration.env', 'runtime.env')
    $missingConfig = $configFiles | Where-Object { !(Test-Path -LiteralPath (Join-Path $runtimeRoot $_)) }
    if ($missingConfig) {
        Write-Host 'First run: creating the local Python environment and seeding the database.'
        $python = Join-Path $serviceRoot '.venv\Scripts\python.exe'
        if (!(Test-Path -LiteralPath $python)) {
            if (!(Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3.11 or newer is required for first-time setup.' }
            & python -m venv (Join-Path $serviceRoot '.venv')
            if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python virtual environment.' }
        }
        & $python -m pip install -e $serviceRoot
        if ($LASTEXITCODE -ne 0) { throw 'Could not install API dependencies. Check the network and Python version.' }
        if (!(Get-Command bun -ErrorAction SilentlyContinue)) { throw 'Bun is required for the initial V3 database migrations.' }
        & (Join-Path $PSScriptRoot 'setup_demo_database.ps1')
    } else {
        # Ordinary launches preserve workflow data and do not reseed the database.
        & $docker.Source compose -p vinhomes-faker-v3 -f (Join-Path $serviceRoot 'docker-compose.demo.yml') up -d --wait
        if ($LASTEXITCODE -ne 0) { throw 'Could not start the V3 database. Check Docker Desktop.' }
    }

    Write-Host '[3/4] Starting FastAPI on port 8000...'
    $python = Join-Path $serviceRoot '.venv\Scripts\python.exe'
    if (!(Test-Path -LiteralPath $python)) { throw 'The API virtual environment is missing. Install the service dependencies first.' }
    & $python (Join-Path $PSScriptRoot 'prepare_demo_database.py') ui
    if ($LASTEXITCODE -ne 0) { throw 'Could not prepare the local UI demo site permissions.' }
    Assert-DemoIdentity
    if ($null -eq (Get-ApiHealth)) {
        if (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue) {
            throw 'Port 8000 is occupied by a service without the expected health endpoint. Stop it before retrying.'
        }
        $python = Join-Path $serviceRoot '.venv\Scripts\python.exe'
        if (!(Test-Path -LiteralPath $python)) { throw 'The API virtual environment is missing. Create services/vinhomes-api/.venv and install the service dependencies.' }
        $startScript = Join-Path $PSScriptRoot 'start_demo.ps1'
        $arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}"' -f $startScript
        $apiProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
            -RedirectStandardOutput (Join-Path $runtimeRoot 'demo-api.stdout.log') `
            -RedirectStandardError (Join-Path $runtimeRoot 'demo-api.stderr.log')
        $apiProcess.Id | Set-Content -LiteralPath (Join-Path $runtimeRoot 'demo-launcher.pid') -Encoding ASCII
    }
    $ready = $false
    $deadline = (Get-Date).AddSeconds(60)
    do {
        try {
            Assert-DemoIdentity
            $apiReady = Invoke-RestMethod -Uri 'http://127.0.0.1:8000/ready' -TimeoutSec 3
            $page = Invoke-WebRequest -Uri $demoUrl -UseBasicParsing -TimeoutSec 3
            $ready = $apiReady.status -eq 'ready' -and $page.StatusCode -eq 200 -and $page.Content.Contains('/demo/assets/business.js')
        } catch { $ready = $false }
        if (!$ready) { Start-Sleep -Seconds 2 }
    } until ($ready -or (Get-Date) -gt $deadline)
    if (!$ready) { throw 'API or demo UI is not ready. See services/vinhomes-api/.local-v3-faker/demo-api.stderr.log. If an older API is already running, stop it and reopen this launcher.' }

    Write-Host '[4/4] Opening the demo UI...'
    Start-Process $demoUrl
    Write-Host "Ready: $demoUrl"
    Write-Host 'Docker, database and API keep running after this window closes. Reopening reuses the running API.'
    exit 0
} catch {
    Write-Host "Startup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

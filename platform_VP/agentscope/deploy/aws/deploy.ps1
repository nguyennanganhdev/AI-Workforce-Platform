param(
    [string]$AwsProfile = "agentscope-deploy",
    [string]$AwsRegion = "ap-southeast-1",
    [string]$ProjectName = "agentscope-prod",
    [string]$PagesProjectName = "ai-workforce-platform-025775",
    [string]$LocalImage = "agentscope-backend:deploy-check"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$InfrastructureDir = $PSScriptRoot
$ProjectRoot = (Resolve-Path (Join-Path $InfrastructureDir "..\..")).Path
$EnvFile = Join-Path $ProjectRoot ".env"
$WebUiDir = Join-Path $ProjectRoot "examples\web_ui"
$FrontendDir = Join-Path $WebUiDir "frontend"
$TfVarsFile = Join-Path $InfrastructureDir "terraform.auto.tfvars.json"
$ResultFile = Join-Path $InfrastructureDir "deployment-result.json"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE"
    }
}

function Read-DotEnv {
    param([string]$Path)
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) { continue }
        $separator = $trimmed.IndexOf("=")
        if ($separator -lt 1) { continue }
        $key = $trimmed.Substring(0, $separator).Trim()
        $value = $trimmed.Substring($separator + 1).Trim()
        if ($value.Length -ge 2) {
            $quoted = ($value.StartsWith('"') -and $value.EndsWith('"')) -or
                ($value.StartsWith("'") -and $value.EndsWith("'"))
            if ($quoted) { $value = $value.Substring(1, $value.Length - 2) }
        }
        $values[$key] = $value
    }
    return $values
}

function New-RandomSecret {
    $bytes = [byte[]]::new(48)
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    return [Convert]::ToBase64String($bytes).TrimEnd("=").Replace("+", "-").Replace("/", "_")
}

function Get-SecretValue {
    param([hashtable]$Values, [string]$Name, [switch]$Generate)
    $value = if ($Values.ContainsKey($Name)) { [string]$Values[$Name] } else { "" }
    if ($Generate -and ([string]::IsNullOrWhiteSpace($value) -or $value -match "^(CHANGE_ME|replace-me)")) {
        return New-RandomSecret
    }
    return $value
}

function Get-TerraformOutput {
    param([string]$Name)
    $value = & terraform output -raw $Name
    if ($LASTEXITCODE -ne 0) { throw "Cannot read Terraform output: $Name" }
    return ([string]$value).Trim()
}

if (-not (Test-Path -LiteralPath $EnvFile)) {
    throw "Missing environment file: $EnvFile"
}

$dotenv = Read-DotEnv -Path $EnvFile
$existingServiceStatus = & aws ecs describe-services --cluster $ProjectName --services "${ProjectName}-api" --profile $AwsProfile --region $AwsRegion --query "services[0].status" --output text 2>$null
$serviceAlreadyDeployed = $LASTEXITCODE -eq 0 -and ([string]$existingServiceStatus).Trim() -eq "ACTIVE"
$initialDesiredCount = if ($serviceAlreadyDeployed) { 1 } else { 0 }
$plainKeys = @(
    "AGENTSCOPE_WORKER_BOOTSTRAP",
    "AUTH_ACCESS_TTL_MINUTES",
    "AUTH_DEFAULT_TENANT_ID",
    "AUTH_JWT_AUDIENCE",
    "AUTH_JWT_ISSUER",
    "AUTH_REFRESH_TTL_DAYS",
    "COLLABORATION_MAX_ACTIVE_SECONDS",
    "COLLABORATION_MAX_EXCHANGES",
    "COLLABORATION_MAX_MODEL_CALLS",
    "COLLABORATION_MAX_TOKENS",
    "COLLABORATION_MAX_VERIFICATIONS",
    "LLM_BACKEND",
    "LLM_BASE_URL",
    "LLM_MODEL_NAME",
    "LOG_LEVEL",
    "MEMORY_EMBEDDING_BASE_URL",
    "MEMORY_EMBEDDING_DIMENSIONS",
    "MEMORY_EMBEDDING_MODEL",
    "MEMORY_EMBEDDING_PASS_DIMENSIONS",
    "MODEL_BASE_URL",
    "MODEL_NAME",
    "MODEL_PROVIDER",
    "REALTIME_MODEL",
    "REME_DEMO_RESET",
    "REME_EMBEDDING_DIMENSIONS",
    "SHARED_CONTEXT_HISTORY_BUDGET_TOKENS",
    "SHARED_CONTEXT_PACKET_MAX_TOKENS",
    "SHARED_CONTEXT_RECENT_HISTORY_RATIO",
    "SHARED_CONTEXT_SUMMARY_ATTEMPTS",
    "SHARED_CONTEXT_SUMMARY_MAX_RATIO",
    "SHARED_CONTEXT_SUMMARY_TRIGGER_RATIO"
)
$appEnvironment = @{}
foreach ($key in $plainKeys) {
    if ($dotenv.ContainsKey($key) -and -not [string]::IsNullOrWhiteSpace([string]$dotenv[$key])) {
        $appEnvironment[$key] = [string]$dotenv[$key]
    }
}

$tfvars = [ordered]@{
    aws_profile        = $AwsProfile
    aws_region         = $AwsRegion
    project_name       = $ProjectName
    pages_project_name = $PagesProjectName
    desired_count      = $initialDesiredCount
    app_environment    = $appEnvironment
}
$utf8 = [Text.UTF8Encoding]::new($false)
[IO.File]::WriteAllText($TfVarsFile, ($tfvars | ConvertTo-Json -Depth 8), $utf8)

Push-Location $InfrastructureDir
try {
    Write-Host "[1/8] Provisioning AWS infrastructure while preserving existing API capacity..."
    Invoke-Checked terraform init -input=false
    Invoke-Checked terraform apply -input=false -auto-approve

    $repository = Get-TerraformOutput "ecr_repository_url"
    $secretArn = Get-TerraformOutput "app_secret_arn"
    $databaseAddress = Get-TerraformOutput "database_address"
    $databasePassword = Get-TerraformOutput "database_password"
    $backendOrigin = Get-TerraformOutput "backend_origin"
    $originVerify = Get-TerraformOutput "origin_verify"
    $cluster = Get-TerraformOutput "ecs_cluster_name"
    $service = Get-TerraformOutput "ecs_service_name"
    $taskDefinition = Get-TerraformOutput "ecs_task_definition_arn"
    $securityGroup = Get-TerraformOutput "ecs_security_group_id"
    $bucket = Get-TerraformOutput "object_bucket"
    $subnets = (& terraform output -json public_subnet_ids | ConvertFrom-Json)
    if ($LASTEXITCODE -ne 0) { throw "Cannot read public_subnet_ids" }

    Write-Host "[2/8] Uploading application secrets to AWS Secrets Manager..."
    $secretValues = [ordered]@{
        AGENTSCOPE_SQL_URL                  = "postgresql+asyncpg://agentscope_admin:${databasePassword}@${databaseAddress}:5432/agentscope"
        AMAP_API_KEY                       = Get-SecretValue $dotenv "AMAP_API_KEY"
        ANTHROPIC_API_KEY                  = Get-SecretValue $dotenv "ANTHROPIC_API_KEY"
        AUTH_JWT_SECRET                    = Get-SecretValue $dotenv "AUTH_JWT_SECRET" -Generate
        AUTH_REFRESH_PEPPER                = Get-SecretValue $dotenv "AUTH_REFRESH_PEPPER" -Generate
        CLAWHUB_API_TOKEN                  = Get-SecretValue $dotenv "CLAWHUB_API_TOKEN"
        DASHSCOPE_API_KEY                  = Get-SecretValue $dotenv "DASHSCOPE_API_KEY"
        GEMINI_API_KEY                     = Get-SecretValue $dotenv "GEMINI_API_KEY"
        LLM_API_KEY                        = Get-SecretValue $dotenv "LLM_API_KEY"
        MEM0_API_KEY                       = Get-SecretValue $dotenv "MEM0_API_KEY"
        MEMORY_EMBEDDING_API_KEY           = Get-SecretValue $dotenv "MEMORY_EMBEDDING_API_KEY"
        OPENAI_API_KEY                     = Get-SecretValue $dotenv "OPENAI_API_KEY"
        PARTNER_API_KEY_PEPPER             = Get-SecretValue $dotenv "PARTNER_API_KEY_PEPPER" -Generate
        PARTNER_API_PROVISIONING_SECRET     = Get-SecretValue $dotenv "PARTNER_API_PROVISIONING_SECRET" -Generate
    }
    $secretFile = Join-Path ([IO.Path]::GetTempPath()) "agentscope-secret-$([Guid]::NewGuid().ToString('N')).json"
    try {
        [IO.File]::WriteAllText($secretFile, ($secretValues | ConvertTo-Json -Compress), $utf8)
        Invoke-Checked aws secretsmanager put-secret-value --secret-id $secretArn --secret-string "file://$secretFile" --profile $AwsProfile --region $AwsRegion --output json
    }
    finally {
        if (Test-Path -LiteralPath $secretFile) { Remove-Item -LiteralPath $secretFile -Force }
    }

    Write-Host "[3/8] Pushing the verified backend image to ECR..."
    $registry = $repository.Split("/")[0]
    $loginPassword = & aws ecr get-login-password --profile $AwsProfile --region $AwsRegion
    if ($LASTEXITCODE -ne 0) { throw "Cannot obtain an ECR login password" }
    $loginPassword | docker login --username AWS --password-stdin $registry
    if ($LASTEXITCODE -ne 0) { throw "Docker login to ECR failed" }
    Invoke-Checked docker image inspect $LocalImage *> $null
    Invoke-Checked docker tag $LocalImage "${repository}:latest"
    Invoke-Checked docker push "${repository}:latest"

    Write-Host "[4/8] Running the PostgreSQL migration as a one-off ECS task..."
    $network = @{
        awsvpcConfiguration = @{
            subnets          = @($subnets)
            securityGroups   = @($securityGroup)
            assignPublicIp   = "ENABLED"
        }
    } | ConvertTo-Json -Compress -Depth 6
    $overrides = @{
        containerOverrides = @(@{
            name    = "app"
            command = @("python", "-m", "alembic", "-c", "/app/src/agentscope/app/storage/_sql/_alembic/alembic.ini", "upgrade", "head")
        })
    } | ConvertTo-Json -Compress -Depth 6
    $networkFile = Join-Path ([IO.Path]::GetTempPath()) "agentscope-network-$([Guid]::NewGuid().ToString('N')).json"
    $overridesFile = Join-Path ([IO.Path]::GetTempPath()) "agentscope-overrides-$([Guid]::NewGuid().ToString('N')).json"
    try {
        [IO.File]::WriteAllText($networkFile, $network, $utf8)
        [IO.File]::WriteAllText($overridesFile, $overrides, $utf8)
        $taskArnOutput = & aws ecs run-task --cluster $cluster --task-definition $taskDefinition --launch-type FARGATE --platform-version LATEST --network-configuration "file://$networkFile" --overrides "file://$overridesFile" --started-by "agentscope-deploy" --query "tasks[0].taskArn" --output text --profile $AwsProfile --region $AwsRegion
        if ($LASTEXITCODE -ne 0) { throw "Failed to start the database migration task" }
        $taskArn = ([string]$taskArnOutput).Trim()
    }
    finally {
        if (Test-Path -LiteralPath $networkFile) { Remove-Item -LiteralPath $networkFile -Force }
        if (Test-Path -LiteralPath $overridesFile) { Remove-Item -LiteralPath $overridesFile -Force }
    }
    if (-not $taskArn -or $taskArn -eq "None") { throw "Failed to start the database migration task" }
    Invoke-Checked aws ecs wait tasks-stopped --cluster $cluster --tasks $taskArn --profile $AwsProfile --region $AwsRegion
    $task = & aws ecs describe-tasks --cluster $cluster --tasks $taskArn --profile $AwsProfile --region $AwsRegion --output json | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0) { throw "Cannot inspect the database migration task" }
    $migrationContainer = $task.tasks[0].containers | Where-Object name -eq "app" | Select-Object -First 1
    if ($migrationContainer.exitCode -ne 0) {
        & aws logs tail "/ecs/$ProjectName" --since 15m --profile $AwsProfile --region $AwsRegion
        throw "Database migration failed with exit code $($migrationContainer.exitCode)"
    }

    Write-Host "[5/8] Starting the AgentScope ECS service..."
    $tfvars.desired_count = 1
    [IO.File]::WriteAllText($TfVarsFile, ($tfvars | ConvertTo-Json -Depth 8), $utf8)
    Invoke-Checked terraform apply -input=false -auto-approve
    Invoke-Checked aws ecs update-service --cluster $cluster --service $service --force-new-deployment --query "service.serviceName" --output text --profile $AwsProfile --region $AwsRegion
    Invoke-Checked aws ecs wait services-stable --cluster $cluster --services $service --profile $AwsProfile --region $AwsRegion

    Write-Host "[6/8] Building the Cloudflare frontend with the same-origin API prefix..."
    Push-Location $WebUiDir
    try {
        $previousApiBase = $env:VITE_API_BASE_URL
        $env:VITE_API_BASE_URL = "/api"
        Invoke-Checked corepack pnpm --filter frontend build
        if ($null -eq $previousApiBase) { Remove-Item Env:VITE_API_BASE_URL -ErrorAction SilentlyContinue }
        else { $env:VITE_API_BASE_URL = $previousApiBase }
    }
    finally {
        Pop-Location
    }

    Write-Host "[7/8] Publishing the frontend and API proxy to Cloudflare Pages..."
    Push-Location $FrontendDir
    try {
        $backendOrigin | npx --yes wrangler@latest pages secret put BACKEND_ORIGIN --project-name $PagesProjectName
        if ($LASTEXITCODE -ne 0) { throw "Cannot set the Cloudflare BACKEND_ORIGIN secret" }
        $originVerify | npx --yes wrangler@latest pages secret put ORIGIN_VERIFY --project-name $PagesProjectName
        if ($LASTEXITCODE -ne 0) { throw "Cannot set the Cloudflare ORIGIN_VERIFY secret" }
        Invoke-Checked npx --yes wrangler@latest pages deploy dist --project-name $PagesProjectName --branch main --commit-dirty=true
    }
    finally {
        Pop-Location
    }

    Write-Host "[8/8] Verifying the public frontend and proxied health endpoint..."
    $frontendOrigin = "https://${PagesProjectName}.pages.dev"
    $healthy = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $health = Invoke-RestMethod -Uri "$frontendOrigin/api/health" -TimeoutSec 30
            if ($null -ne $health) { $healthy = $true; break }
        }
        catch {
            Start-Sleep -Seconds 10
        }
    }
    if (-not $healthy) { throw "Public health check did not become ready: $frontendOrigin/api/health" }
    $pageReady = $false
    for ($attempt = 1; $attempt -le 30; $attempt++) {
        try {
            $page = Invoke-WebRequest -Uri "$frontendOrigin/chat" -TimeoutSec 30 -UseBasicParsing
            if ($page.StatusCode -eq 200) { $pageReady = $true; break }
        }
        catch {
            Start-Sleep -Seconds 10
        }
    }
    if (-not $pageReady) { throw "Frontend /chat did not become ready: $frontendOrigin/chat" }

    $result = [ordered]@{
        frontend = "$frontendOrigin/chat"
        api_health = "$frontendOrigin/api/health"
        backend_origin = $backendOrigin
        aws_region = $AwsRegion
        ecs_cluster = $cluster
        object_bucket = $bucket
        deployed_at = [DateTimeOffset]::UtcNow.ToString("o")
    }
    [IO.File]::WriteAllText($ResultFile, ($result | ConvertTo-Json), $utf8)
    Write-Host "Deployment completed: $frontendOrigin/chat"
}
finally {
    Pop-Location
}


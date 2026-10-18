resource "aws_ecr_repository" "app" {
  name                 = "${var.project_name}/backend"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the ten newest images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 30
}

resource "aws_ecs_cluster" "app" {
  name = var.project_name

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

locals {
  infrastructure_environment = {
    AUTH_ENABLED                   = "true"
    AUTH_COOKIE_SECURE             = "true"
    CORS_ALLOWED_ORIGINS           = "https://${var.pages_project_name}.pages.dev"
    SHARED_CONTEXT_STORAGE_BACKEND = "sql"
    REDIS_HOST                     = aws_elasticache_replication_group.cache.primary_endpoint_address
    REDIS_PORT                     = "6379"
    REDIS_DB                       = "0"
    REDIS_SSL                      = "true"
    S3_ENABLED                     = "true"
    S3_BUCKET                      = aws_s3_bucket.objects.id
    AWS_DEFAULT_REGION             = var.aws_region
    QDRANT_PATH                    = "/app/data/qdrant"
    UVICORN_RELOAD                 = "false"
  }

  container_environment = [
    for key, value in merge(var.app_environment, local.infrastructure_environment) : {
      name  = key
      value = value
    }
  ]

  secret_keys = toset([
    "AGENTSCOPE_SQL_URL",
    "AMAP_API_KEY",
    "ANTHROPIC_API_KEY",
    "AUTH_JWT_SECRET",
    "AUTH_REFRESH_PEPPER",
    "CLAWHUB_API_TOKEN",
    "DASHSCOPE_API_KEY",
    "GEMINI_API_KEY",
    "LLM_API_KEY",
    "MEM0_API_KEY",
    "MEMORY_EMBEDDING_API_KEY",
    "OPENAI_API_KEY",
    "PARTNER_API_KEY_PEPPER",
    "PARTNER_API_PROVISIONING_SECRET",
  ])

  container_secrets = [
    for key in local.secret_keys : {
      name      = key
      valueFrom = "${aws_secretsmanager_secret.app.arn}:${key}::"
    }
  ]
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.project_name
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = tostring(var.ecs_cpu)
  memory                   = tostring(var.ecs_memory)
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  runtime_platform {
    cpu_architecture        = "X86_64"
    operating_system_family = "LINUX"
  }

  volume {
    name = "workspaces"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.app.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.workspaces.id
        iam             = "DISABLED"
      }
    }
  }

  volume {
    name = "qdrant"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.app.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.qdrant.id
        iam             = "DISABLED"
      }
    }
  }

  container_definitions = jsonencode([{
    name      = "app"
    image     = "${aws_ecr_repository.app.repository_url}:latest"
    essential = true

    portMappings = [{
      name          = "http"
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
      appProtocol   = "http"
    }]

    environment = local.container_environment
    secrets     = local.container_secrets

    mountPoints = [
      {
        sourceVolume  = "workspaces"
        containerPath = "/app/examples/agent_service/workspaces"
        readOnly      = false
      },
      {
        sourceVolume  = "qdrant"
        containerPath = "/app/data/qdrant"
        readOnly      = false
      },
    ]

    linuxParameters = { initProcessEnabled = true }
    stopTimeout     = 120

    healthCheck = {
      command     = ["CMD-SHELL", "curl --fail --silent http://localhost:8000/health || exit 1"]
      interval    = 30
      timeout     = 10
      retries     = 5
      startPeriod = 120
    }

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "app"
      }
    }
  }])

  depends_on = [
    aws_efs_mount_target.app,
    aws_iam_role_policy.ecs_execution_secrets,
    aws_iam_role_policy_attachment.ecs_execution,
  ]
}

resource "aws_lb" "api" {
  name               = substr("${var.project_name}-api", 0, 32)
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 300

  enable_deletion_protection = false
  drop_invalid_header_fields = true
}

resource "aws_lb_target_group" "api" {
  name        = substr("${var.project_name}-api", 0, 32)
  port        = 8000
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  deregistration_delay = 60

  health_check {
    enabled             = true
    path                = "/health"
    matcher             = "200"
    interval            = 30
    timeout             = 10
    healthy_threshold   = 2
    unhealthy_threshold = 5
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"
    fixed_response {
      content_type = "text/plain"
      message_body = "Forbidden"
      status_code  = "403"
    }
  }
}

resource "aws_lb_listener_rule" "cloudfront" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 1

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  condition {
    http_header {
      http_header_name = "X-Origin-Verify"
      values           = [random_password.origin_header.result]
    }
  }
}

resource "aws_ecs_service" "app" {
  name            = "${var.project_name}-api"
  cluster         = aws_ecs_cluster.app.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  platform_version                  = "LATEST"
  health_check_grace_period_seconds = 300
  wait_for_steady_state             = true
  propagate_tags                    = "SERVICE"

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "app"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener_rule.cloudfront]
}


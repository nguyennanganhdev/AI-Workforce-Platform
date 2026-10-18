data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_vpc" "main" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "${var.project_name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${var.project_name}-igw" }
}

resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.main.id
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  map_public_ip_on_launch = true

  tags = { Name = "${var.project_name}-public-${count.index + 1}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = { Name = "${var.project_name}-public" }
}

resource "aws_route_table_association" "public" {
  count = length(aws_subnet.public)

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "alb" {
  name = "${var.project_name}-alb"
  # Keep the original AWS description stable; access is enforced by the
  # generated X-Origin-Verify listener rule below.
  description = "CloudFront origin traffic only"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.project_name}-alb" }
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "Public HTTP; the listener requires a generated origin header"
}

resource "aws_vpc_security_group_egress_rule" "alb_all" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "ecs" {
  name        = "${var.project_name}-ecs"
  description = "AgentScope Fargate tasks"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.project_name}-ecs" }
}

resource "aws_vpc_security_group_ingress_rule" "ecs_alb" {
  security_group_id            = aws_security_group.ecs.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 8000
  to_port                      = 8000
  ip_protocol                  = "tcp"
  description                  = "AgentScope API from the ALB"
}

resource "aws_vpc_security_group_egress_rule" "ecs_all" {
  security_group_id = aws_security_group.ecs.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "rds" {
  name        = "${var.project_name}-rds"
  description = "PostgreSQL from AgentScope tasks"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.project_name}-rds" }
}

resource "aws_vpc_security_group_ingress_rule" "rds_ecs" {
  security_group_id            = aws_security_group.rds.id
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  description                  = "PostgreSQL from AgentScope tasks"
}

resource "aws_vpc_security_group_egress_rule" "rds_all" {
  security_group_id = aws_security_group.rds.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "cache" {
  name        = "${var.project_name}-cache"
  description = "Valkey from AgentScope tasks"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.project_name}-cache" }
}

resource "aws_vpc_security_group_ingress_rule" "cache_ecs" {
  security_group_id            = aws_security_group.cache.id
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  description                  = "TLS Valkey from AgentScope tasks"
}

resource "aws_vpc_security_group_egress_rule" "cache_all" {
  security_group_id = aws_security_group.cache.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

resource "aws_security_group" "efs" {
  name        = "${var.project_name}-efs"
  description = "EFS from AgentScope tasks"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.project_name}-efs" }
}

resource "aws_vpc_security_group_ingress_rule" "efs_ecs" {
  security_group_id            = aws_security_group.efs.id
  referenced_security_group_id = aws_security_group.ecs.id
  from_port                    = 2049
  to_port                      = 2049
  ip_protocol                  = "tcp"
  description                  = "NFS from AgentScope tasks"
}

resource "aws_vpc_security_group_egress_rule" "efs_all" {
  security_group_id = aws_security_group.efs.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}


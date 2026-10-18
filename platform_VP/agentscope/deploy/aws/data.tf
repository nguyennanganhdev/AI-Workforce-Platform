resource "random_id" "bucket" {
  byte_length = 4
}

resource "random_password" "database" {
  length  = 32
  special = false
}

resource "random_password" "origin_header" {
  length  = 40
  special = false
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db"
  subnet_ids = aws_subnet.public[*].id
}

resource "aws_db_instance" "postgres" {
  identifier = "${var.project_name}-postgres"

  engine                 = "postgres"
  engine_version         = "17.9"
  instance_class         = "db.t4g.micro"
  db_name                = "agentscope"
  username               = "agentscope_admin"
  password               = random_password.database.result
  port                   = 5432
  allocated_storage      = 20
  max_allocated_storage  = 100
  storage_type           = "gp3"
  storage_encrypted      = true
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  backup_retention_period    = 1
  backup_window              = "18:00-19:00"
  maintenance_window         = "sun:19:30-sun:20:30"
  auto_minor_version_upgrade = true
  apply_immediately          = true
  deletion_protection        = false
  skip_final_snapshot        = true
  copy_tags_to_snapshot      = true
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-cache"
  subnet_ids = aws_subnet.public[*].id
}

resource "aws_elasticache_replication_group" "cache" {
  replication_group_id = "${var.project_name}-cache"
  description          = "AgentScope durable cache and message bus"

  engine                     = "valkey"
  engine_version             = "8.2"
  node_type                  = "cache.t4g.micro"
  port                       = 6379
  num_cache_clusters         = 1
  automatic_failover_enabled = false
  multi_az_enabled           = false
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  apply_immediately          = true
  snapshot_retention_limit   = 1
  snapshot_window            = "17:00-18:00"
  maintenance_window         = "sun:20:30-sun:21:30"

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.cache.id]
}

resource "aws_efs_file_system" "app" {
  encrypted        = true
  performance_mode = "generalPurpose"
  throughput_mode  = "bursting"

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = { Name = "${var.project_name}-persistent" }
}

resource "aws_efs_backup_policy" "app" {
  file_system_id = aws_efs_file_system.app.id

  backup_policy {
    status = "ENABLED"
  }
}

resource "aws_efs_mount_target" "app" {
  count = length(aws_subnet.public)

  file_system_id  = aws_efs_file_system.app.id
  subnet_id       = aws_subnet.public[count.index].id
  security_groups = [aws_security_group.efs.id]
}

resource "aws_efs_access_point" "workspaces" {
  file_system_id = aws_efs_file_system.app.id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/workspaces"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "0770"
    }
  }
}

resource "aws_efs_access_point" "qdrant" {
  file_system_id = aws_efs_file_system.app.id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/qdrant"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "0770"
    }
  }
}

resource "aws_s3_bucket" "objects" {
  bucket = "${var.project_name}-objects-${random_id.bucket.hex}"
}

resource "aws_s3_bucket_public_access_block" "objects" {
  bucket = aws_s3_bucket.objects.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "objects" {
  bucket = aws_s3_bucket.objects.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_versioning" "objects" {
  bucket = aws_s3_bucket.objects.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_cors_configuration" "objects" {
  bucket = aws_s3_bucket.objects.id

  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["GET", "HEAD", "POST", "PUT"]
    allowed_origins = ["https://${var.pages_project_name}.pages.dev"]
    expose_headers  = ["ETag"]
    max_age_seconds = 3600
  }
}


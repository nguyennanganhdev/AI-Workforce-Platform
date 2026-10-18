output "aws_region" {
  value = var.aws_region
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.app.name
}

output "ecs_service_name" {
  value = aws_ecs_service.app.name
}

output "ecs_task_definition_arn" {
  value = aws_ecs_task_definition.app.arn
}

output "ecs_security_group_id" {
  value = aws_security_group.ecs.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}

output "app_secret_arn" {
  value = aws_secretsmanager_secret.app.arn
}

output "database_address" {
  value = aws_db_instance.postgres.address
}

output "database_password" {
  value     = random_password.database.result
  sensitive = true
}

output "cache_address" {
  value = aws_elasticache_replication_group.cache.primary_endpoint_address
}

output "object_bucket" {
  value = aws_s3_bucket.objects.id
}

output "backend_origin" {
  value = "http://${aws_lb.api.dns_name}"
}

output "origin_verify" {
  value     = random_password.origin_header.result
  sensitive = true
}

output "frontend_origin" {
  value = "https://${var.pages_project_name}.pages.dev"
}


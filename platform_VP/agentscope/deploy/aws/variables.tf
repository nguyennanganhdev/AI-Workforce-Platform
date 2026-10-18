variable "aws_profile" {
  description = "AWS CLI profile used by Terraform."
  type        = string
  default     = "agentscope-deploy"
}

variable "aws_region" {
  description = "AWS region for the deployment."
  type        = string
  default     = "ap-southeast-1"
}

variable "project_name" {
  description = "Short prefix used for AWS resources."
  type        = string
  default     = "agentscope-prod"
}

variable "pages_project_name" {
  description = "Cloudflare Pages project that serves the frontend."
  type        = string
  default     = "ai-workforce-platform-025775"
}

variable "desired_count" {
  description = "Number of AgentScope ECS tasks. Keep at one while Qdrant uses its local EFS store."
  type        = number
  default     = 0

  validation {
    condition     = var.desired_count >= 0 && var.desired_count <= 1
    error_message = "desired_count must be zero or one while local Qdrant storage is enabled."
  }
}

variable "app_environment" {
  description = "Non-secret application environment values copied from the local .env file."
  type        = map(string)
  default     = {}
}

variable "ecs_cpu" {
  type    = number
  default = 1024
}

variable "ecs_memory" {
  type    = number
  default = 3072
}


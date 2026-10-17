variable "aws_region" {
  description = "AWS region for TechPulse."
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "project_name" {
  description = "Resource naming prefix."
  type        = string
  default     = "techpulse"
}

variable "frontend_allowed_origins" {
  description = "Origins allowed to call the API. Set to the CloudFront URL for deployed environments."
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "ai_provider" {
  description = "AI provider integration is wired in a later increment; this variable documents the intended provider."
  type        = string
  default     = "bedrock"
  validation {
    condition     = contains(["bedrock", "external"], var.ai_provider)
    error_message = "ai_provider must be bedrock or external."
  }
}

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
  description = "Origins allowed to call API."
  type        = list(string)
  default     = ["http://localhost:5173"]
}

variable "ses_from_address" {
  description = "Verified SES sender address. Configure for environments that send email."
  type        = string
  default     = ""
}

variable "cognito_callback_urls" {
  description = "Allowed hosted UI callback URLs."
  type        = list(string)
  default     = ["http://localhost:5173/"]
}

variable "cognito_logout_urls" {
  description = "Allowed hosted UI logout URLs."
  type        = list(string)
  default     = ["http://localhost:5173/"]
}

variable "ai_model_id" {
  description = "Approved Bedrock model ID. Blank disables model invocation."
  type        = string
  default     = ""
}

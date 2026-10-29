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

variable "cognito_domain_prefix" {
  description = "Globally unique Cognito hosted UI domain prefix. Blank derives one from project, environment, and AWS account ID."
  type        = string
  default     = ""
}

variable "ai_model_id" {
  description = "Approved Bedrock model ID. Blank disables model invocation."
  type        = string
  default     = ""
}

variable "cloudflare_frontend_url" {
  description = "Public HTTPS URL of the Cloudflare Workers frontend."
  type        = string
  default     = "https://techpulse.narsapurkarthik.workers.dev"
  validation {
    condition     = startswith(var.cloudflare_frontend_url, "https://")
    error_message = "cloudflare_frontend_url must use HTTPS."
  }
}

variable "workspace_relevance_provider" {
  description = "Workspace relevance provider: groq (free-tier API key), anthropic (paid Claude API key), or deterministic (keyword rules, no key). Keys live in Secrets Manager."
  type        = string
  # Free keyword-rules sorting; restore this default if no AI provider key is available.
  # default     = "deterministic"
  default = "groq"
  validation {
    condition     = contains(["groq", "anthropic", "deterministic"], var.workspace_relevance_provider)
    error_message = "workspace_relevance_provider must be groq, anthropic, or deterministic."
  }
}

variable "workspace_relevance_secret_name" {
  description = "Optional Secrets Manager fallback for the relevance API key. Blank disables Secrets Manager reads."
  type        = string
  default     = ""
}

variable "workspace_relevance_api_key" {
  description = "Relevance provider API key, passed from the GitHub secret TECHPULSE_RELEVANCE_API_KEY."
  type        = string
  default     = ""
  sensitive   = true
}

variable "workspace_relevance_model_id" {
  description = "Model ID for the relevance provider. Blank uses the provider default (groq: openai/gpt-oss-20b, anthropic: claude-haiku-5-5)."
  type        = string
  default     = ""
}

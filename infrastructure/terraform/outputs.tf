output "aws_account_id" {
  value       = data.aws_caller_identity.current.account_id
  description = "AWS account where TechPulse is deployed."
}

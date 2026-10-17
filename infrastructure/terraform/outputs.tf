output "api_endpoint" {
  value       = aws_apigatewayv2_api.http.api_endpoint
  description = "API Gateway endpoint."
}

output "frontend_url" {
  value       = "https://${aws_cloudfront_distribution.frontend.domain_name}"
  description = "CloudFront URL for the TechPulse frontend."
}

output "updates_table_name" {
  value = aws_dynamodb_table.updates.name
}

output "ingestion_queue_url" {
  value = aws_sqs_queue.ingestion.url
}

output "aws_account_id" {
  value       = data.aws_caller_identity.current.account_id
  description = "AWS account where TechPulse is deployed."
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

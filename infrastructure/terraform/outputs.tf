output "api_endpoint" {
  value       = aws_apigatewayv2_api.http.api_endpoint
  description = "API Gateway endpoint."
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

output "frontend_bucket_name" {
  value       = aws_s3_bucket.frontend.bucket
  description = "Private S3 bucket that stores built frontend assets."
}

output "cloudfront_distribution_id" {
  value       = aws_cloudfront_distribution.frontend.id
  description = "CloudFront distribution ID for frontend cache invalidation."
}

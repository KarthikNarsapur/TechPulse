provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "TechPulse"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  name = "${var.project_name}-${var.environment}"
  cognito_domain_prefix = var.cognito_domain_prefix != "" ? var.cognito_domain_prefix : "${var.project_name}-${var.environment}-${data.aws_caller_identity.current.account_id}"
  common_environment = {
    TECHPULSE_ENVIRONMENT    = var.environment
    TECHPULSE_AWS_REGION     = var.aws_region
    TECHPULSE_UPDATES_TABLE  = aws_dynamodb_table.updates.name
    TECHPULSE_SOURCES_TABLE  = aws_dynamodb_table.sources.name
    TECHPULSE_ANALYSES_TABLE = aws_dynamodb_table.analyses.name
    TECHPULSE_DELIVERIES_TABLE = aws_dynamodb_table.deliveries.name
    TECHPULSE_SUBSCRIPTIONS_TABLE = aws_dynamodb_table.subscriptions.name
    TECHPULSE_SUBSCRIPTION_TECH_INDEX = "technology-index"
    TECHPULSE_SES_FROM_ADDRESS = var.ses_from_address
    TECHPULSE_UPDATE_INDEX   = "technology-published-index"
    TECHPULSE_MODEL_ID      = var.ai_model_id
    TECHPULSE_CORS_ORIGINS  = join(",", concat(var.frontend_allowed_origins, ["https://${aws_cloudfront_distribution.frontend.domain_name}"]))
    TECHPULSE_ANALYSIS_QUEUE_URL = aws_sqs_queue.analysis.url
    TECHPULSE_NOTIFICATIONS_QUEUE_URL = aws_sqs_queue.notifications.url
  }
}

resource "aws_dynamodb_table" "updates" {
  name         = "${local.name}-updates"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "update_id"

  attribute {
    name = "update_id"
    type = "S"
  }
  attribute {
    name = "technology"
    type = "S"
  }
  attribute {
    name = "published_key"
    type = "S"
  }
  attribute {
    name = "feed_scope"
    type = "S"
  }

  global_secondary_index {
    name            = "technology-published-index"
    hash_key        = "technology"
    range_key       = "published_key"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "published-index"
    hash_key        = "feed_scope"
    range_key       = "published_key"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = var.environment == "prod"
  }
  server_side_encryption {
    enabled = true
  }
}

resource "aws_dynamodb_table" "sources" {
  name         = "${local.name}-sources"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "source_id"

  attribute {
    name = "source_id"
    type = "S"
  }
  point_in_time_recovery {
    enabled = var.environment == "prod"
  }
  server_side_encryption {
    enabled = true
  }
}

resource "aws_dynamodb_table" "analyses" {
  name         = "${local.name}-analyses"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "update_id"
  range_key    = "analysis_version"

  attribute {
    name = "update_id"
    type = "S"
  }
  attribute {
    name = "analysis_version"
    type = "S"
  }
  point_in_time_recovery {
    enabled = var.environment == "prod"
  }
  server_side_encryption {
    enabled = true
  }
}

resource "aws_dynamodb_table" "subscriptions" {
  name         = "${local.name}-subscriptions"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "technology_id"

  attribute {
    name = "user_id"
    type = "S"
  }
  attribute {
    name = "technology_id"
    type = "S"
  }
  global_secondary_index {
    name            = "technology-index"
    hash_key        = "technology_id"
    range_key       = "user_id"
    projection_type = "ALL"
  }
  point_in_time_recovery {
    enabled = var.environment == "prod"
  }
  server_side_encryption {
    enabled = true
  }
}

resource "aws_dynamodb_table" "deliveries" {
  name         = "${local.name}-deliveries"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "delivery_id"

  attribute {
    name = "delivery_id"
    type = "S"
  }
  point_in_time_recovery {
    enabled = var.environment == "prod"
  }
  server_side_encryption {
    enabled = true
  }
}

resource "aws_sqs_queue" "ingestion_dlq" {
  name                      = "${local.name}-ingestion-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}
resource "aws_sqs_queue" "ingestion" {
  name                       = "${local.name}-ingestion"
  visibility_timeout_seconds = 900
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 10
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.ingestion_dlq.arn
    maxReceiveCount     = 4
  })
}
resource "aws_sqs_queue" "analysis_dlq" {
  name                      = "${local.name}-analysis-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}
resource "aws_sqs_queue" "analysis" {
  name                       = "${local.name}-analysis"
  visibility_timeout_seconds = 180
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 10
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.analysis_dlq.arn
    maxReceiveCount     = 4
  })
}
resource "aws_sqs_queue" "notifications_dlq" {
  name                      = "${local.name}-notifications-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}
resource "aws_sqs_queue" "notifications" {
  name                       = "${local.name}-notifications"
  visibility_timeout_seconds = 180
  message_retention_seconds  = 345600
  receive_wait_time_seconds  = 10
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.notifications_dlq.arn
    maxReceiveCount     = 4
  })
}

resource "aws_iam_role" "lambda_execution" {
  name = "${local.name}-lambda-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_execution.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}
resource "aws_iam_role_policy" "lambda_data" {
  name = "${local.name}-data-access"
  role = aws_iam_role.lambda_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query", "dynamodb:Scan"]
      Resource = [
        aws_dynamodb_table.updates.arn, "${aws_dynamodb_table.updates.arn}/index/*",
        aws_dynamodb_table.sources.arn, aws_dynamodb_table.analyses.arn,
        aws_dynamodb_table.subscriptions.arn, aws_dynamodb_table.deliveries.arn
      ]
    }]
  })
}
resource "aws_iam_role_policy" "lambda_queue_access" {
  name = "${local.name}-queue-access"
  role = aws_iam_role.lambda_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = ["sqs:SendMessage"]
        Resource = [aws_sqs_queue.ingestion.arn, aws_sqs_queue.analysis.arn, aws_sqs_queue.notifications.arn]
      },
      {
        Effect = "Allow"
        Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"]
        Resource = [aws_sqs_queue.ingestion.arn, aws_sqs_queue.analysis.arn, aws_sqs_queue.notifications.arn]
      }
    ]
  })
}
resource "aws_iam_role_policy" "lambda_ai_email" {
  name = "${local.name}-ai-email"
  role = aws_iam_role.lambda_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["bedrock:InvokeModel"], Resource = "*" },
      { Effect = "Allow", Action = ["ses:SendEmail", "ses:SendRawEmail"], Resource = "*" },
      {
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = ["arn:${data.aws_partition.current.partition}:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:techpulse-${var.environment}-notifications-*"]
      }
    ]
  })
}

resource "aws_lambda_function" "api" {
  function_name    = "${local.name}-api"
  role             = aws_iam_role.lambda_execution.arn
  filename         = "${path.module}/dist/api.zip"
  source_code_hash = fileexists("${path.module}/dist/api.zip") ? filebase64sha256("${path.module}/dist/api.zip") : null
  handler          = "app.handlers.api.handler"
  runtime          = "python3.12"
  timeout          = 15
  memory_size      = 512
  publish          = true

  environment {
    variables = local.common_environment
  }
  depends_on = [aws_iam_role_policy_attachment.lambda_basic, aws_iam_role_policy.lambda_data]
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_lambda_function" "dispatch" {
  function_name    = "${local.name}-dispatch"
  role             = aws_iam_role.lambda_execution.arn
  filename         = "${path.module}/dist/workers.zip"
  source_code_hash = fileexists("${path.module}/dist/workers.zip") ? filebase64sha256("${path.module}/dist/workers.zip") : null
  handler          = "app.handlers.dispatch.handler"
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 256
  publish          = true

  environment {
    variables = merge(local.common_environment, {
      TECHPULSE_INGESTION_QUEUE_URL = aws_sqs_queue.ingestion.url
    })
  }
  depends_on = [aws_iam_role_policy_attachment.lambda_basic, aws_iam_role_policy.lambda_data, aws_iam_role_policy.lambda_queue_access]
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_lambda_function" "ingest" {
  function_name    = "${local.name}-ingest"
  role             = aws_iam_role.lambda_execution.arn
  filename         = "${path.module}/dist/workers.zip"
  source_code_hash = fileexists("${path.module}/dist/workers.zip") ? filebase64sha256("${path.module}/dist/workers.zip") : null
  handler          = "app.handlers.ingest.handler"
  runtime          = "python3.12"
  timeout          = 120
  memory_size      = 512
  publish          = true

  environment {
    variables = local.common_environment
  }
  depends_on = [aws_iam_role_policy_attachment.lambda_basic, aws_iam_role_policy.lambda_data, aws_iam_role_policy.lambda_queue_access]
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_lambda_function" "analyze" {
  function_name    = "${local.name}-analyze"
  role             = aws_iam_role.lambda_execution.arn
  filename         = "${path.module}/dist/workers.zip"
  source_code_hash = fileexists("${path.module}/dist/workers.zip") ? filebase64sha256("${path.module}/dist/workers.zip") : null
  handler          = "app.handlers.analyze.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 512
  publish          = true

  environment {
    variables = local.common_environment
  }
  depends_on = [aws_iam_role_policy_attachment.lambda_basic, aws_iam_role_policy.lambda_data, aws_iam_role_policy.lambda_ai_email, aws_iam_role_policy.lambda_queue_access]
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_lambda_function" "notify" {
  function_name    = "${local.name}-notify"
  role             = aws_iam_role.lambda_execution.arn
  filename         = "${path.module}/dist/workers.zip"
  source_code_hash = fileexists("${path.module}/dist/workers.zip") ? filebase64sha256("${path.module}/dist/workers.zip") : null
  handler          = "app.handlers.notify.handler"
  runtime          = "python3.12"
  timeout          = 60
  memory_size      = 512
  publish          = true

  environment {
    variables = local.common_environment
  }
  depends_on = [aws_iam_role_policy_attachment.lambda_basic, aws_iam_role_policy.lambda_data, aws_iam_role_policy.lambda_ai_email, aws_iam_role_policy.lambda_queue_access]
  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_lambda_event_source_mapping" "ingest_queue" {
  event_source_arn                   = aws_sqs_queue.ingestion.arn
  function_name                      = aws_lambda_function.ingest.arn
  batch_size                         = 5
  function_response_types            = ["ReportBatchItemFailures"]
  maximum_batching_window_in_seconds = 5
}
resource "aws_lambda_event_source_mapping" "analysis_queue" {
  event_source_arn        = aws_sqs_queue.analysis.arn
  function_name           = aws_lambda_function.analyze.arn
  batch_size              = 5
  function_response_types = ["ReportBatchItemFailures"]
}
resource "aws_lambda_event_source_mapping" "notification_queue" {
  event_source_arn        = aws_sqs_queue.notifications.arn
  function_name           = aws_lambda_function.notify.arn
  batch_size              = 5
  function_response_types = ["ReportBatchItemFailures"]
}

resource "aws_scheduler_schedule_group" "main" {
  name = "${local.name}-schedules"
}
resource "aws_iam_role" "scheduler" {
  name = "${local.name}-scheduler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}
resource "aws_iam_role_policy" "scheduler_invoke_dispatcher" {
  name = "${local.name}-scheduler-invoke-dispatcher"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = [aws_lambda_function.dispatch.arn]
    }]
  })
}
resource "aws_scheduler_schedule" "source_poll" {
  name                         = "${local.name}-source-poll"
  group_name                   = aws_scheduler_schedule_group.main.name
  schedule_expression          = "rate(30 minutes)"
  schedule_expression_timezone = "UTC"
  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.dispatch.arn
    role_arn = aws_iam_role.scheduler.arn
    input    = jsonencode({ action = "poll_enabled_sources" })
    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
  }
  depends_on = [aws_iam_role_policy.scheduler_invoke_dispatcher]
}

resource "aws_apigatewayv2_api" "http" {
  name          = "${local.name}-api"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = distinct(concat(var.frontend_allowed_origins, ["https://${aws_cloudfront_distribution.frontend.domain_name}"]))
    allow_methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    allow_headers = ["authorization", "content-type", "idempotency-key"]
    max_age       = 3600
  }
}
resource "aws_apigatewayv2_integration" "api_lambda" {
  api_id                 = aws_apigatewayv2_api.http.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
}
resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowApiGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http.execution_arn}/*/*"
}

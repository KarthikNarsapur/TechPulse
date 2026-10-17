resource "aws_lambda_function" "dispatch" {
  function_name    = "${local.name}-dispatch"
  role             = aws_iam_role.lambda_execution.arn
  filename         = "${path.module}/dist/workers.zip"
  source_code_hash = fileexists("${path.module}/dist/workers.zip") ? filebase64sha256("${path.module}/dist/workers.zip") : null
  handler           = "app.handlers.dispatch.handler"
  runtime           = "python3.12"
  timeout           = 30
  memory_size       = 256
  publish           = true

  environment {
    variables = merge(local.common_environment, {
      TECHPULSE_INGESTION_QUEUE_URL = aws_sqs_queue.ingestion.url
    })
  }

  depends_on = [aws_iam_role_policy_attachment.lambda_basic, aws_iam_role_policy.lambda_data]

  lifecycle {
    ignore_changes = [filename, source_code_hash]
  }
}

resource "aws_iam_role_policy" "dispatcher_enqueue" {
  name = "${local.name}-dispatcher-enqueue"
  role = aws_iam_role.lambda_execution.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage"]
      Resource = [aws_sqs_queue.ingestion.arn]
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

# Replace the initial schedule target with the lightweight dispatcher.
resource "aws_scheduler_schedule" "source_poll" {
  name                          = "${local.name}-source-poll"
  group_name                    = aws_scheduler_schedule_group.main.name
  schedule_expression           = "rate(30 minutes)"
  schedule_expression_timezone  = "UTC"
  flexible_time_window { mode = "OFF" }

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

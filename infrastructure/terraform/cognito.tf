resource "aws_cognito_user_pool" "main" {
  name = "${local.name}-users"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 3
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }
}

resource "aws_cognito_user_pool_domain" "main" {
  domain       = local.cognito_domain_prefix
  user_pool_id = aws_cognito_user_pool.main.id
}

resource "aws_cognito_user_pool_client" "web" {
  name         = "${local.name}-web"
  user_pool_id = aws_cognito_user_pool.main.id

  generate_secret                      = false
  prevent_user_existence_errors         = "ENABLED"
  enable_token_revocation               = true
  explicit_auth_flows                   = ["ALLOW_USER_SRP_AUTH", "ALLOW_REFRESH_TOKEN_AUTH"]
  allowed_oauth_flows_user_pool_client  = true
  allowed_oauth_flows                   = ["code"]
  allowed_oauth_scopes                  = ["openid", "email", "profile"]
  callback_urls                         = distinct(concat(var.cognito_callback_urls, ["https://${aws_cloudfront_distribution.frontend.domain_name}/"]))
  logout_urls                           = distinct(concat(var.cognito_logout_urls, ["https://${aws_cloudfront_distribution.frontend.domain_name}/"]))
  supported_identity_providers          = ["COGNITO"]
  access_token_validity                 = 60
  id_token_validity                     = 60
  refresh_token_validity                = 30
  token_validity_units {
    access_token  = "minutes"
    id_token      = "minutes"
    refresh_token = "days"
  }
}

resource "aws_apigatewayv2_authorizer" "jwt" {
  api_id           = aws_apigatewayv2_api.http.id
  name             = "${local.name}-jwt"
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.web.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}

resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.http.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
}

resource "aws_apigatewayv2_route" "technologies" {
  api_id             = aws_apigatewayv2_api.http.id
  route_key          = "GET /api/v1/technologies"
  target             = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "updates" {
  api_id             = aws_apigatewayv2_api.http.id
  route_key          = "GET /api/v1/updates"
  target             = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "update_detail" {
  api_id             = aws_apigatewayv2_api.http.id
  route_key          = "GET /api/v1/updates/{update_id}"
  target             = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.main.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "cognito_hosted_ui_url" {
  description = "Cognito hosted UI base URL for the frontend auth code flow."
  value       = "https://${aws_cognito_user_pool_domain.main.domain}.auth.${var.aws_region}.amazoncognito.com"
}


resource "aws_apigatewayv2_route" "subscriptions_list" {
  api_id             = aws_apigatewayv2_api.http.id
  route_key          = "GET /api/v1/subscriptions"
  target             = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "subscriptions_put" {
  api_id             = aws_apigatewayv2_api.http.id
  route_key          = "PUT /api/v1/subscriptions/{technology_id}"
  target             = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "subscriptions_delete" {
  api_id             = aws_apigatewayv2_api.http.id
  route_key          = "DELETE /api/v1/subscriptions/{technology_id}"
  target             = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}

resource "aws_apigatewayv2_route" "source_status" {
  api_id             = aws_apigatewayv2_api.http.id
  route_key          = "GET /api/v1/source-status"
  target             = "integrations/${aws_apigatewayv2_integration.api_lambda.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.jwt.id
}


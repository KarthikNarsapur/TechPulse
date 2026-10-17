# TechPulse Terraform

This directory defines the first serverless infrastructure baseline.

## Current components

- HTTP API Gateway and API Lambda
- Ingestion, analysis, and notification Lambda functions
- DynamoDB tables and a technology/published-time GSI
- SQS queues and dead-letter queues
- EventBridge Scheduler trigger
- Shared execution role for the initial bootstrap

## Packaging

The Lambda zip files are expected at:

- `infrastructure/terraform/dist/api.zip`
- `infrastructure/terraform/dist/workers.zip`

Package from the backend directory so the zip contains the `app/` package and the runtime dependencies. The packaging script and CI workflow will be added in the next increment.

## Important bootstrap limitations

This is not yet production-ready infrastructure. API authorization, dedicated least-privilege Lambda roles, complete queue fan-out permissions, notification secrets, frontend hosting, log retention, alarms, and source persistence orchestration are still being implemented. Do not apply to a production account until those items are closed and a Terraform plan is reviewed.

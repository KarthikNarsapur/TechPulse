# TechPulse

Serverless cloud and DevOps release intelligence portal.

TechPulse discovers official technology announcements, normalizes and deduplicates updates, generates source-grounded AI summaries, ranks potential impact, and distributes relevant changes through the portal and notifications.

## Pilot scope

Initial technology groups: AWS, Azure, Google Cloud, Kubernetes, Terraform, and GitLab. The source registry is extensible; additional tools can be added through RSS/Atom, vendor API, GitHub Releases API, or GitHub release Atom feeds.

## Architecture

- **Frontend:** React + TypeScript, built as static assets for S3 + CloudFront.
- **API:** API Gateway + Python Lambda (FastAPI + Mangum).
- **Scheduling:** EventBridge Scheduler triggers a dispatcher Lambda.
- **Async processing:** SQS queues and dead-letter queues for ingestion, analysis, and notifications.
- **Persistence:** DynamoDB tables designed around feed, source, subscription, analysis, and delivery access patterns.
- **AI:** One structured model call per new content version; deterministic priority/deadline rules.
- **Notifications:** Amazon SES initially, with Slack and Microsoft Teams adapters designed as additional channels.
- **IaC:** Terraform.
- **Operations:** CloudWatch logs, metrics, alarms, and dead-letter queue monitoring.

## Repository layout

- `frontend/` — standalone web application.
- `backend/` — API, domain models, and application services.
- `workers/` — ingestion, analysis, and notification Lambda handlers.
- `source-registry/` — source configuration.
- `infrastructure/terraform/` — serverless infrastructure.
- `tests/` — unit and contract tests.
- `docs/` — architecture, source validation, security, and operations.

## Development status

This repository is being bootstrapped in increments. The first milestone is a tested vertical slice of source registry, feed parsing, normalization, deduplication contracts, and Lambda entry points. Production deployment requires source endpoint verification, AWS account configuration, an approved AI model, and notification credentials.

## Local development

Python backend and workers use Python 3.12. See `backend/pyproject.toml` for commands and dependencies.

Never commit AWS credentials, model API keys, SES credentials, Slack webhooks, or Teams webhook URLs. Use environment variables locally and AWS Secrets Manager / IAM roles in AWS.

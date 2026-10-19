# TechPulse

**Serverless cloud and DevOps release intelligence portal.**

TechPulse collects official cloud, infrastructure, Kubernetes, and DevOps announcements, turns them into normalized updates, optionally enriches each new content revision with AI-generated summaries, applies deterministic priority rules, and routes relevant updates to subscribers.

The initial pilot covers **AWS, Azure, Google Cloud, Kubernetes, Terraform, and GitLab**. Source definitions are data-driven so additional vendors and repositories can be onboarded without redesigning the processing pipeline.

> **Deployment note:** The AWS deployment workflow is manually triggered from GitHub Actions. Its current actions are **Apply** and **Destroy**. Apply creates a Terraform plan and applies that exact plan in the same run, then publishes Lambda code and frontend assets. A successful infrastructure apply is not, by itself, proof that all live source endpoints, AI configuration, or notification channels are fully configured.

## How TechPulse gets updates

TechPulse is designed to pull updates from **official vendor and project sources**, rather than scraping arbitrary websites.

Supported source types currently implemented in the backend:

- **RSS / Atom feeds** — release notes, service announcements, and vendor engineering updates.
- **GitHub Releases API** — recent releases for a configured `owner/repository`.
- **GitHub release Atom feeds** — can be represented as a feed source where the official repository provides one.

The source list is maintained in [`source-registry/sources.yaml`](source-registry/sources.yaml). Each entry describes the source identity and technology, vendor, endpoint or repository, adapter type, and whether the source is enabled. The registry loader validates entries and requires unique `source_id` values. Only enabled entries are scheduled for polling.

**Adding a source:** validate that it is an official, reachable source; add a correctly configured entry to the registry; test its format and timestamps; and verify that the adapter normalizes its content as expected. Do not mark a source as verified just because its URL exists. Authentication, pagination, rate limits, redirects, and source-specific behavior should be tested where relevant.

## End-to-end processing flow

```text
Official RSS / Atom feeds or GitHub Releases
                  |
                  v
        EventBridge Scheduler
                  |
                  v
          Dispatcher Lambda
                  |
                  v
          Ingestion SQS queue
                  |
                  v
           Ingestion Lambda
       fetch -> parse -> normalize
                  |
                  v
      DynamoDB canonical updates
       (new or revised content)
                  |
                  v
          Analysis SQS queue
                  |
                  v
           Analysis Lambda
      AI summary + classification
       deterministic priority rules
                  |
                  v
     Technology subscriptions lookup
                  |
                  v
        Notification SQS queue
                  |
                  v
          Notification Lambda
           /             \
          v               v
     Amazon SES       Slack / Teams
                       via Secrets
```

### 1. Schedule and dispatch

Amazon EventBridge Scheduler invokes the dispatcher Lambda. The dispatcher reads enabled source definitions from the persisted source table when available, falling back to the checked-in source registry, then sends one message per enabled source to the ingestion SQS queue. The queue decouples polling work from the scheduler.

### 2. Fetch and normalize source content

The ingestion Lambda consumes source IDs from SQS and selects the corresponding configured adapter:

- The feed adapter fetches and parses RSS/Atom XML.
- The GitHub Releases adapter calls the GitHub Releases API for the configured repository.

Entries without a usable title or canonical link are skipped. The adapters normalize fields such as source ID, vendor, technology, title, canonical URL, publication time, observation time, source-specific external ID, text content, and a content fingerprint. This gives downstream services a common update format even when vendors publish different formats.

### 3. Deduplicate and detect revisions

Normalized updates are written through the update store in DynamoDB. A repeated item is not treated as a new announcement merely because the next scheduled poll sees it again. TechPulse compares its stable update identity and content fingerprint to distinguish a **new update**, an unchanged item, and a **materially changed revision**.

New and changed revisions are queued for analysis. The ingestion worker also records source poll status, including completion timestamps, fetched counts, new/changed counts, and sanitized failure information. Failed source jobs can be retried through SQS and inspected through operational status/logs.

### 4. Generate AI analysis

The analysis Lambda loads the canonical update and checks for an existing analysis using a cache key derived from the content hash, model ID, and prompt version. When a matching analysis is not available, it calls the configured analysis provider for a structured result.

The model is intended to summarize and classify the source material—not to invent release facts or make the final priority decision. **Priority and deadline logic are deterministic**, which keeps those decisions consistent and testable. Source content is untrusted input; instructions embedded in release notes must not be followed as system instructions.

AI analysis requires a model ID and valid provider configuration. If the model is not configured, this capability will not work simply because the infrastructure has deployed.

### 5. Match subscriptions

After analysis, TechPulse looks up enabled subscriptions for the update's technology. It builds a stable delivery identifier from the update revision, subscriber, and channel so a retry can be recognized as the same logical notification.

Only supported, configured destinations are eligible. Email requires a recipient. Slack and Microsoft Teams require a reference to a TechPulse-managed secret; raw webhook URLs are not placed in queue messages.

### 6. Deliver notifications

The notification Lambda processes queued deliveries:

- **Email:** Amazon Simple Email Service (SES).
- **Chat:** Slack or Microsoft Teams webhooks resolved from AWS Secrets Manager.

A DynamoDB delivery record provides a conditional claim/lease so duplicate SQS deliveries do not normally resend a notification that has already been marked sent. Failed or interrupted jobs can be retried, with dead-letter queues available for messages that cannot be processed successfully.

### 7. Display updates in the portal

The React + TypeScript frontend calls the FastAPI backend through API Gateway. The backend reads persisted update, analysis, technology, and subscription data from DynamoDB. The frontend is built as static assets and hosted from Amazon S3 behind CloudFront. Cognito authenticates users; protected API routes use a JWT authorizer.

## Architecture and AWS components

| Component | Responsibility |
|---|---|
| React + TypeScript | Web portal and subscription UI |
| Amazon S3 + CloudFront | Static frontend hosting and CDN |
| Amazon API Gateway + FastAPI Lambda | HTTP API |
| Amazon Cognito | User authentication |
| EventBridge Scheduler | Periodic source polling trigger |
| Dispatcher Lambda | Enqueue enabled source IDs |
| Ingestion Lambda + SQS | Fetch, parse, normalize, deduplicate |
| Analysis Lambda + SQS | AI analysis, deterministic priority, subscription matching |
| Notification Lambda + SQS | Email/chat delivery and delivery idempotency |
| DynamoDB | Sources, updates, analyses, subscriptions, poll status, and delivery records |
| AWS Secrets Manager | Secret-backed chat webhook configuration |
| Amazon SES | Email delivery |
| Terraform | Infrastructure as code |
| CloudWatch and SQS DLQs | Logs and failure investigation |

For the more detailed design, see [Architecture](docs/architecture.md), [Security](docs/security.md), and [Source validation](docs/source-validation.md).

## Repository layout

- `.github/workflows/` — CI and manual AWS deployment workflows.
- `frontend/` — React + TypeScript application.
- `backend/app/api.py` — FastAPI routes.
- `backend/app/adapters/` — RSS/Atom and GitHub Releases adapters.
- `backend/app/source_registry.py` — source registry loading and validation.
- `backend/app/handlers/` — API, dispatch, ingestion, analysis, and notification Lambda handlers.
- `backend/app/storage.py` — DynamoDB storage operations.
- `backend/app/ai_provider.py` — analysis-provider integration.
- `source-registry/sources.yaml` — source definitions and enablement.
- `infrastructure/terraform/` — AWS resources and Terraform configuration.
- `tests/` — automated tests.
- `docs/` — architecture, deployment, development, security, and validation notes.

## Deploy to AWS using GitHub Actions

Deployment is started manually; it does not require a local checkout.

1. Open **GitHub → Actions → Deploy TechPulse to AWS**.
2. Select the branch containing the workflow.
3. Choose the target environment (for example, `dev`) and AWS region (for example, `ap-south-1`).
4. Choose **Apply** to deploy or update the environment. The workflow packages the Lambda code, bootstraps the encrypted/versioned Terraform state bucket if needed, initializes Terraform, validates configuration, creates a plan, and applies that plan in the same run.
5. After Terraform succeeds, the workflow updates Lambda function code, builds the frontend using deployed API/Cognito endpoints, syncs the build to S3, invalidates CloudFront, and checks the API health endpoint.
6. Review the workflow logs and final health-check result. Open the printed frontend URL to test the portal.

Choose **Destroy** only when you intend to remove the selected environment. You must enter the exact confirmation text `DESTROY`. Destruction can remove resources and data, so verify the selected environment before confirming.

The workflow authenticates to AWS with GitHub OIDC and the `AWS_DEPLOY_ROLE_ARN` repository/environment secret. It uses remote S3 state with encryption, versioning, public-access blocking, and native state locking. See [GitHub Actions deployment guide](docs/deploy-github-actions.md) for IAM setup and operational notes.

## Configuration and operational prerequisites

Deployment creates infrastructure, but some integrations need separate configuration:

- **Source quality:** Confirm official endpoints, feed formats, release identity, timestamps, and polling behavior.
- **AI analysis:** Configure a supported model ID and permissions/provider settings. Analysis will fail if the model is not configured.
- **Email:** Configure and verify the SES sender address and ensure the AWS account/region has the required SES sending access.
- **Slack / Teams:** Store webhook values in AWS Secrets Manager and configure subscriptions to reference the corresponding secret IDs. Do not put webhook URLs directly into source code or queue payloads.
- **Users:** Cognito is configured for the pilot sign-in flow; user provisioning may require an administrator action.
- **Observability:** Inspect CloudWatch logs, source poll status, SQS retry behavior, and dead-letter queues when updates or notifications are missing.

## Local development and tests

The backend and Lambda handlers use **Python 3.12**. The frontend uses Node.js and npm. See:

- [Development guide](docs/development.md)
- [Source validation guide](docs/source-validation.md)
- [Security notes](docs/security.md)
- [Roadmap](docs/roadmap.md)

Run the repository's tests before promoting changes. Use mocks/fake analysis providers for tests that should not call AWS or a live AI model.

## Security notes

- Do not commit AWS access keys, model API keys, SES credentials, Slack webhooks, Teams webhook URLs, Terraform state, or plan files.
- Use GitHub OIDC and least-privilege IAM rather than long-lived AWS keys.
- Keep notification webhooks in AWS Secrets Manager. Queue messages should carry secret references, not secret values.
- Treat vendor release text as untrusted external content.
- Keep dev/pilot limitations explicit; do not use this deployment as production-ready until IAM separation, monitoring/alarms, source validation, and live integration testing have been reviewed.

# TechPulse Implementation Roadmap

## Increment 1 — Serverless foundation (current PR)

- [x] Establish repository structure and developer documentation.
- [x] Define canonical update/source/analysis models.
- [x] Add RSS/Atom and generic GitHub Releases adapters.
- [x] Add Lambda handler entry points for API, dispatch, ingestion, analysis, and notifications.
- [x] Add DynamoDB access helpers and indexed feed access patterns.
- [x] Add API Gateway, Lambda, EventBridge Scheduler, SQS/DLQs, DynamoDB, Cognito, CloudFront, and S3 Terraform.
- [x] Add a standalone React dashboard shell and Cognito Hosted UI PKCE login.
- [x] Add backend/frontend/Terraform CI checks.
- [ ] Validate live payloads for every initial source before enabling it.
- [ ] Wire canonical update revisions so a changed source item triggers re-analysis.
- [ ] Complete an end-to-end local/staging test using a fixture feed and a fake AI provider.

## Increment 2 — Complete the first useful vertical slice

- [ ] Make source polling status/checkpoints durable and visible in the admin page.
- [ ] Finish idempotent handling when an announcement changes after first ingestion.
- [ ] Implement a provider interface for AI and add mocked-provider tests.
- [ ] Implement technology subscriptions and user read/saved state APIs.
- [ ] Implement an explicit notification eligibility service using subscriptions and team mapping.
- [ ] Add persisted delivery claims, provider outcomes, retries, and delivery history.
- [ ] Resolve chat webhook references through Secrets Manager; reject URLs supplied by user-facing API calls.
- [ ] Add digest generation and SES sender configuration checks.
- [ ] Add a basic admin source-management API, restricted by role.

## Increment 3 — Production pilot hardening

- [ ] Replace shared Lambda execution role with per-function least-privilege roles.
- [ ] Add a bounded outbound host policy and redirect validation for source fetches.
- [ ] Add alarms for stale sources, queue age, Lambda errors, and dead-letter queue depth.
- [ ] Test Cognito sign-in, token expiry, logout, and role enforcement end-to-end.
- [ ] Run Terraform plan in the target sandbox and review all proposed changes.
- [ ] Verify SES sender/domain and notification destination configuration.
- [ ] Run recovery, duplicate-delivery, malformed-feed, prompt-injection, and SSRF test cases.
- [ ] Pilot with a small cloud/DevOps group and tune noise/priority rules using feedback.

## Increment 4 — Expand technology coverage

- [ ] Add curated source entries for Helm, Argo CD, Docker, Jenkins, Istio, Prometheus, Grafana, OpenTelemetry, and other requested tools.
- [ ] Prefer official RSS/API/GitHub release metadata over arbitrary HTML scraping.
- [ ] Track CLI releases separately from provider/plugin releases where appropriate.
- [ ] Use source validation to test parser contracts and record last verified time.
- [ ] Introduce a dedicated search service only if the DynamoDB feed queries no longer meet measured needs.

## Non-negotiable release gates

- Source facts must retain canonical official URLs.
- AI output must be schema-validated and must not invent unknown versions or deadlines.
- Final priority is deterministic, reviewable, and independent of the model's prose.
- SQS-triggered handlers must be idempotent and use partial-batch failure responses.
- No user-configurable URL may be fetched by privileged collectors without validation.
- No production infrastructure is deployed without a reviewed Terraform plan.

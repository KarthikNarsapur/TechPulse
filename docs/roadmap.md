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
- [x] Add canonical URL revision detection and enqueue re-analysis when an announcement's content hash changes.
- [ ] Validate live payloads for every initial source before enabling it.
- [ ] Archive prior source content in revision history (current record carries a revision counter).
- [x] Add a deterministic local integration test from fixture RSS feed through persistence and analysis using a fake provider (live staging run remains pending).
- [x] Add subscription-based notification fan-out after successful AI analysis.

## Increment 2 — Complete the first useful vertical slice

- [x] Persist per-source poll attempts, start/completion timestamps, outcomes, item counts, and sanitized error types in DynamoDB; expose authenticated status API and dashboard panel.
- [x] Add automated tests for Lambda ingestion behavior on new, changed, unchanged, and failed source polls.
- [x] Implement an injectable structured AI provider interface and mocked-provider contract tests.
- [x] Implement user-scoped technology subscription list/create/delete APIs behind the Cognito JWT authorizer.
- [x] Add dashboard controls to subscribe/unsubscribe from email alerts per technology.
- [x] Implement user-scoped read/saved update state APIs and dashboard controls.
- [x] Implement initial notification eligibility by enabled technology subscriptions.
- [x] Add persisted delivery claims, provider outcomes, retry recovery, and delivery status.
- [x] Resolve chat webhook references through Secrets Manager and reject raw webhook URLs.
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

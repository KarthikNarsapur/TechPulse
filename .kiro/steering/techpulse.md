---
inclusion: always
---

# TechPulse — Kiro Project Steering

## Mission and product requirements

TechPulse is a serverless cloud and DevOps release-intelligence portal. It collects official vendor/project announcements, normalizes them into a unified feed, optionally enriches updates with AI summaries and priority, and supports user subscriptions and notifications.

The initial supported technologies are **AWS, Azure, Google Cloud (GCP), Kubernetes, Terraform, and GitLab**.

The core user outcome is genuine updates from the **last 7 days**, working controls, and trustworthy source-health information. Never show demo/sample content as if it were a real announcement.

## Architecture

- **Frontend:** React + TypeScript + Vite. Main dashboard: frontend/src/App.tsx; API client: frontend/src/api.ts.
- **Authentication:** Amazon Cognito; API requests use the access token managed by frontend/src/auth.ts.
- **API:** FastAPI in backend/app/api.py, deployed to AWS Lambda with Mangum and exposed through API Gateway HTTP API.
- **Persistence:** DynamoDB tables for updates, sources, polling status, subscriptions, analyses, deliveries, and per-user state.
- **Asynchronous ingestion:** EventBridge Scheduler invokes the dispatcher every 30 minutes. The dispatcher queues source jobs in SQS; ingestion fetches/parses sources and stores normalized updates. Analysis and notification work use separate queues/Lambdas.
- **Source configuration:** source-registry/sources.yaml. Registry loading/validation: backend/app/source_registry.py. Adapters: backend/app/adapters/.
- **Infrastructure:** Terraform in infrastructure/terraform/.
- **Deployment:** GitHub Actions in .github/workflows/. The AWS deployment workflow is manually triggered and provides Apply and Destroy. Never trigger Destroy or change live infrastructure as routine debugging.

Follow existing architecture and naming patterns before introducing services, dependencies, data stores, or frameworks.

## Department workspaces and shared cross-workspace updates

This is a product requirement for the department-based experience. Build separate, persistent workspaces for departments, while keeping one shared update catalog underneath.

### Core interaction rule

- Each department has its own workspace identity, landing view, saved preferences, and department-focused default feed.
- A user can discover and read updates relevant to other departments **inside their current workspace**. Cross-department access must not switch the active workspace, change its URL/context unexpectedly, or reset the user's workspace-specific filters and state.
- Use in-workspace filters, related-update sections, technology views, or a shared-catalog search to expose cross-department updates. Make the update's originating/relevant department(s) clear.
- An update may be relevant to multiple departments. Model this as many-to-many relevance, not by duplicating the underlying update record per workspace.
- Keep one canonical update record and canonical URL. Workspace views are filtered/shared views over that catalog.
- Distinguish an update's **source technology** (AWS, Azure, GCP, Kubernetes, Terraform, GitLab, etc.) from its **department relevance**. Technology and department are separate dimensions.
- Do not require users to change workspaces just to view Terraform or Kubernetes updates while working in Migration and FinOps.
- Preserve the current active workspace when opening a cross-department update and when returning to the feed.
- Respect authentication and authorization for any department-specific or restricted content. Do not assume that a job title alone grants access to sensitive data.

### Department hierarchy

Use the supplied employee directory's department labels as the canonical starting taxonomy. Preserve parent/child relationships:

- **General**
- **Tech Consulting (TC)**
  - TC - General
  - TC - Data and AIoT
  - TC - Migration and FinOps
  - TC - DevOps & Kubernetes
  - TC - Development
  - TC - L&D, Content
  - TC - Pre-Sales
- **Training Sales (TS)**
  - TS - MS Programs
  - TS - Corporate Accounts
  - TS - Inside Sales Management
  - TS - Demand Generation
- **HR & OD**
  - HR & Finance

Keep TC as the primary product focus and sensible default for the initial implementation, but do not hard-code the application so other departments cannot be used. Use stable department IDs internally and human-readable labels in the UI. Normalize whitespace and punctuation for mapping/import purposes without silently renaming the visible labels.

The supplied directory maps job titles to departments, including repeated titles. Do not treat job titles as unique employee identifiers, and do not invent employee names or identities. If user-to-department membership is introduced, use a reliable user identity and an explicit directory/membership mapping; define a safe default for users whose department is unknown.

### Relevance behavior and examples

- In **TC - Migration and FinOps**, show migration/FinOps-focused updates by default and allow users to view Kubernetes, Terraform, cloud infrastructure, security, and other cross-team updates in the same workspace.
- A Terraform or Kubernetes update can be relevant to both TC - DevOps & Kubernetes and TC - Migration and FinOps when the content supports both. Do not classify solely from a keyword if context suggests otherwise.
- General/cross-team updates should be accessible from relevant department workspaces without duplicating stored update records.
- Users can filter/search by technology and relevance department without navigating away from the active workspace.
- If relevance is uncertain, classify as cross-team/general or mark it for review rather than confidently assigning an unsupported department.

### Implementation and migration guidance

Before coding, inspect the current data models, API routes, frontend routing/state, DynamoDB keys/indexes, user-state storage, and tests. Propose a minimal data model for stable department IDs, parent IDs, user workspace preference, and update-to-department relevance. Keep compatibility with existing updates and users; existing updates should remain visible through a sensible General/cross-team fallback until classified.

Implement the shared catalog and workspace views without creating duplicate update rows per department. Add tests proving that cross-department browsing leaves the active workspace unchanged, technology filters work inside a workspace, multi-department relevance works, unknown departments fail safely, and existing update records remain accessible. Document any required migration and deploy steps. Do not make live infrastructure or destructive data changes without explicit approval.

## Current pilot sources

The checked-in source registry defines the initial pilot: official RSS/Atom endpoints and GitHub Releases API sources for AWS, Azure, GCP, Kubernetes, Terraform, and GitLab. Verify endpoint reachability, response format, timestamp parsing, stable identity, and successful polling. An enabled source is not necessarily a healthy source.

Prefer official vendor/project feeds and APIs. Avoid scraping arbitrary sites when an official source exists. If a source needs a new format, implement a small explicit adapter with tests and documented failure behavior.

## Refresh updates: current known-good behavior

The user has confirmed that the **Refresh updates** button is now working. Treat the previously reported no-op as resolved; do not describe it as an active defect or start by re-investigating it without new evidence.

Preserve the end-to-end behavior when changing this feature:

1. The frontend handler in frontend/src/App.tsx shows a busy/loading state and visible success or failure feedback.
2. frontend/src/api.ts sends the authenticated request to POST /api/v1/refresh and handles non-2xx responses clearly.
3. The FastAPI route authenticates the user, validates required configuration, and queues ingestion jobs for enabled sources.
4. API Gateway/Terraform route configuration, Lambda environment variables, and least-privilege SQS permissions remain aligned.
5. Dispatcher and ingestion use the checked-in source registry, queue source jobs, fetch and parse sources, and persist normalized updates.
6. The UI reloads the feed and source status as appropriate. Ingestion is asynchronous: distinguish a request accepted/queued from a source fetch completing and a new update appearing.

When modifying refresh behavior, add or preserve regression coverage for success and error paths, and run the relevant checks. Only reopen investigation of the previously fixed issue if a reproducible regression or new evidence appears. Do not claim runtime verification beyond what was actually tested.

## Feed correctness and seven-day window

- The frontend requests days=7 and limit=100. Preserve this default unless product requirements explicitly change.
- Filter using a valid publication timestamp; use observation time only when publication time is absent and document that fallback.
- Normalize timestamps to UTC. Handle missing, malformed, or timezone-naive dates safely.
- Display genuine stored records only. If no records exist, show a clear empty state and actionable guidance; never substitute a demo card or fabricated URL.
- Every card link must point to that update's canonical URL, not the repository homepage unless the update is genuinely about that repository.
- AWS Transform or other product-specific announcements may not be present in a general RSS feed. When an announcement is missing, inspect the official endpoint, source health, parser output, stored record, API filtering, and frontend filters. Add a source/adapter only after verifying an official endpoint.

## Reliability and observability

- Give every user action meaningful loading, success, empty, and error states.
- Source status should show last attempt, last success, failure reason, and fetched/new/changed counts when available.
- Distinguish **refresh requested/queued**, **source fetch completed**, and **new updates displayed**. They are different states.
- Do not swallow exceptions without logs and user-visible feedback. Never log tokens, credentials, or sensitive provider responses.
- Use bounded network timeouts, sensible retries/backoff, and safe handling of HTTP errors, malformed XML/JSON, missing timestamps, rate limits, and duplicate records.
- Keep ingestion idempotent; stable source/update identities and revisions should prevent duplicate records.

## All controls must work

Audit every visible dashboard action and ensure it performs its advertised operation. Verify at least:
- Refresh updates
- Technology filters and search
- Bookmark/save and per-user update state
- Subscription enable/disable and removal
- Source polling status
- Sign in, sign out, and authenticated API calls
- Navigation arrows and external links

Verify the full UI → API → backend → persistence/integration path where applicable. If a control is not implemented or cannot work in the current deployment, disable it with an explicit explanation rather than leaving a dead button. Do not use clickable-looking decorative controls with no handler.

## Development workflow

1. Inspect relevant files, tests, recent commits, workflows, and current behavior before editing.
2. State a concise root-cause hypothesis and verify it with evidence.
3. Implement the smallest maintainable end-to-end fix.
4. Add regression tests. Run available frontend lint/build/tests, backend tests, and Terraform format/validate as relevant. If a check cannot run, state that rather than claiming it passed.
5. Review the diff for security, unintended infrastructure changes, secret leakage, compatibility, and fake/mock data.
6. Commit to the intended branch with a descriptive message. Do not claim deployment or live success until the workflow and runtime behavior have been verified.
7. Report root cause, files changed, actual test results, commit SHA, deployment needed, and remaining uncertainty.

## Security and infrastructure guardrails

- Never commit credentials, tokens, private keys, .env files, or customer data. Use environment variables and existing secret-management patterns.
- Preserve Cognito/API Gateway authentication and authorization. Never trust identity supplied in a request body/query; use verified JWT claims.
- Use least-privilege IAM and keep secrets out of frontend bundles.
- Avoid destructive data/infrastructure changes. Do not run Destroy or delete live resources unless the user explicitly asks.
- Keep Terraform as the source of truth; avoid console-only configuration assumptions.
- Avoid changing unrelated resources or deployment behavior while fixing bugs.

## Documentation

Update README and relevant technical docs when behavior, source support, environment variables, deployment steps, or troubleshooting changes. Document required configuration and verification steps. Do not document unverified behavior as working.

## Definition of done

A fix is done only when user-visible behavior is correct, errors are actionable, regression tests cover the defect, relevant checks pass (or unrun checks are identified), runtime behavior is verified where possible, fake data/misleading success states are absent, and documentation reflects the actual shipped behavior.

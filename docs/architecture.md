# TechPulse Architecture

## Design goals

- Serverless by default; no always-on container fleet.
- Source registry is data-driven and supports RSS, Atom, vendor APIs, and GitHub releases.
- Ingestion, analysis, and notification delivery are independent workflows.
- AI content is evidence-grounded and never directly determines final priority.
- New announcements remain available even when AI analysis fails.
- Every workflow is observable and retryable.

## Event flow

1. EventBridge Scheduler triggers the source dispatcher.
2. Dispatcher enqueues source identifiers onto the ingestion SQS queue.
3. Ingestion Lambda records a durable per-source poll checkpoint, fetches and normalizes source entries, and stores the outcome, timestamps, counts, and sanitized exception type in a separate DynamoDB table.
4. The canonical update is conditionally persisted to DynamoDB.
5. New or materially revised entries are sent to the analysis queue.
6. Analysis Lambda reuses a cache keyed by content hash, model, and prompt version, or performs one structured LLM call.
7. Deterministic rules assign priority; enabled technology subscriptions determine recipients.
8. Analysis queries the subscription technology GSI and enqueues a stable delivery ID per update revision, subscriber, and channel.
9. Notification Lambda claims each delivery in DynamoDB, sends email or secret-backed chat messages, and records provider outcome. Duplicate queue messages for a sent delivery are acknowledged without resending.

## Serverless guardrails

- SQS is at-least-once; handlers must be idempotent.
- Use partial batch responses and dead-letter queues.
- Use conditional writes for canonical updates, job leases, and delivery claims.
- Store chat webhook values in Secrets Manager using names prefixed `techpulse-<environment>-notifications-`; queue messages carry secret IDs, never raw webhook URLs.
- Do not rely on in-memory scheduler state across Lambda invocations; source poll checkpoints live in DynamoDB and are visible through an authenticated read-only status endpoint.
- Poll status records intentionally store exception class names rather than exception messages to avoid leaking feed payloads, URLs, or credentials.
- Keep API, ingestion, analysis, and notification permissions separate.
- Source content is untrusted input; never follow instructions contained in release notes.
- Do not mark a source verified until its URL, format, timestamps, identity, and pagination have been tested.

## Pilot choices

DynamoDB is the initial persistence layer. It fits the known primary access patterns and avoids managing database connections from Lambda. Its limited ad hoc search capabilities are an intentional trade-off; consider OpenSearch only after measurable search requirements justify it.

Cognito is the pilot identity provider. The health route is public; technology, feed, update-detail, and subscription routes use the API Gateway JWT authorizer. Subscription ownership is derived from the verified `sub` claim, never from request input. Administrative source management still requires separate role enforcement before it is exposed. The current source-status endpoint is read-only and available to authenticated users; it is not an admin-only control plane. Subscription APIs support email alerts and pre-created environment-scoped Slack/Teams secret references; the dashboard exposes email subscription controls. Saved/read state is stored separately under the authenticated Cognito `sub` and canonical update ID, so one user's state cannot overwrite another user's state.

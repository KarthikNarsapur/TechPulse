# Security Design

## Identity and authorization

- API Gateway must use a configured JWT authorizer before production rollout.
- Derive the principal from validated claims, not a user ID in the request body.
- Keep administrative source management separate from employee preferences.
- Add audit records for source changes, policy changes, and manual runs.

## Source fetching

- Only administrators may create or activate sources.
- Restrict sources to approved public domains and explicitly allowed API hosts.
- Validate redirects at every hop; block private, loopback, link-local, and metadata-service destinations.
- Apply response-size, connect-timeout, total-timeout, and redirect limits.
- Do not allow arbitrary URLs from unauthenticated API requests to reach collectors.
- Use user-agent identification and respect provider rate limits.

## AI and external content

- Treat content from feeds, release bodies, and documentation as untrusted.
- Never interpret source content as system instructions.
- Require schema-constrained output and reject malformed output.
- Require evidence for release dates, version claims, and deprecation statements.
- Preserve original source references and model/prompt identifiers.
- Use only an approved model service and send the minimum necessary content.

## AWS

- Use separate Lambda roles with least-privilege access.
- Keep secrets in Secrets Manager; do not commit tokens or webhook URLs.
- Enable encryption in transit and at rest.
- Configure CloudWatch alarms for failures, queue age, and dead-letter messages.
- Use Terraform plans and approvals before production deployment.

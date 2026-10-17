# Source Validation

The registry contains candidate official sources, not an assertion that every URL has passed a live integration test.

## Validation checklist

For each source, capture:
- Official source page and owner
- Exact feed/API URL derived from that page
- HTTP status and content type
- Payload parsing success
- Stable entry ID, canonical URL, and publication timestamp
- Pagination/cursor behavior and historical window
- Last verified date, parser version, and fixture payload
- Rate limit and retry policy

## Enablement policy

- New candidate: `unverified`, disabled by default
- Successful fixture and live test: `verified`
- Repeated parser/fetch errors: `degraded`
- Manually disabled: `disabled`

Do not interpret an empty response as success unless the fetch and parsing checks succeed. Keep source health separate from update count.

## Initial source groups

- AWS What's New and service-specific announcements
- Azure Updates (exact feed endpoint must be confirmed from the live official page)
- Google Cloud release notes (use current documented feed/API)
- Kubernetes releases and security advisories
- Terraform CLI and selected provider releases
- GitLab monthly/patch release feeds
- Generic GitHub Releases API/Atom adapter for the long tail

The registry URL may be an API endpoint, but the source link presented to users should be the canonical human-readable release page where available.

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

## Running the validator

Install the backend runtime requirements, then run from the repository root:

```bash
pip install -r backend/requirements.txt
python scripts/validate_sources.py --all --json
```

Use `--all` to include disabled candidate feeds. Use `--strict` when validating only the selected (enabled by default) sources and require every selected source to return at least one parseable entry. The tool prints a report and intentionally catches failures per source so the remaining sources are still checked. It is not run on every CI build because transient vendor outages and rate limits would make CI unreliable; run it during source onboarding and before enabling a feed.

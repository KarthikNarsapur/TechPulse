"""Generic GitHub Releases API adapter."""
from datetime import datetime, timezone
from typing import Any

import httpx

from app.models import NormalizedUpdate, SourceConfig


def _parse_datetime(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def fetch_github_releases(source: SourceConfig, *, timeout_seconds: float = 15.0) -> list[NormalizedUpdate]:
    """Fetch recent GitHub releases for configured owner/repo.

    For production, add persisted pagination/checkpoints and conditional requests.
    """
    if not source.repository or "/" not in source.repository:
        raise ValueError("github_releases sources require repository='owner/repo'")
    owner, repo = source.repository.split("/", maxsplit=1)
    endpoint = f"https://api.github.com/repos/{owner}/{repo}/releases"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "TechPulse/0.1",
    }
    with httpx.Client(timeout=timeout_seconds, headers=headers, follow_redirects=False) as client:
        response = client.get(endpoint, params={"per_page": 30})
        response.raise_for_status()
        payload: Any = response.json()

    if not isinstance(payload, list):
        raise ValueError(f"Unexpected GitHub Releases response for {source.source_id}")

    updates: list[NormalizedUpdate] = []
    for release in payload:
        if not isinstance(release, dict):
            continue
        if release.get("draft"):
            continue
        if release.get("prerelease") and not source.include_prereleases:
            continue
        url = str(release.get("html_url") or "").strip()
        title = str(release.get("name") or release.get("tag_name") or "").strip()
        if not url or not title:
            continue
        body = " ".join(str(release.get("body") or "").split())[:20000]
        external_id = str(release.get("id") or release.get("tag_name") or url)
        content_hash = NormalizedUpdate.fingerprint(
            source.source_id, external_id, url, title, body
        )
        updates.append(
            NormalizedUpdate(
                update_id=NormalizedUpdate.make_id(url),
                source_id=source.source_id,
                vendor=source.vendor,
                technology=source.technology,
                title=title[:500],
                canonical_url=url,
                published_at=_parse_datetime(release.get("published_at")),
                observed_at=datetime.now(timezone.utc),
                content_text=body,
                content_hash=content_hash,
                external_id=external_id,
            )
        )
    return updates

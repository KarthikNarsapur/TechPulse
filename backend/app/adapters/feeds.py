"""RSS/Atom and GitHub release-feed adapters."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from app.models import NormalizedUpdate, SourceConfig


DEFAULT_USER_AGENT = "TechPulse/0.1 (+internal engineering release intelligence)"


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _entry_timestamp(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        return datetime(*parsed[:6], tzinfo=timezone.utc)
    return _parse_datetime(entry.get("published") or entry.get("updated"))


def fetch_feed(source: SourceConfig, *, timeout_seconds: float = 15.0) -> list[NormalizedUpdate]:
    """Fetch an RSS/Atom URL and normalize entries.

    The registry must be restricted to validated official sources. Network
    egress controls and redirect validation should be enforced in deployment.
    """
    with httpx.Client(
        timeout=timeout_seconds,
        follow_redirects=True,
        max_redirects=3,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml",
        },
    ) as client:
        response = client.get(str(source.url))
        response.raise_for_status()

    parsed = feedparser.parse(response.content)
    if parsed.bozo and not parsed.entries:
        raise ValueError(f"Feed could not be parsed for source {source.source_id}")

    updates: list[NormalizedUpdate] = []
    for entry in parsed.entries:
        title = str(entry.get("title", "")).strip()
        link = str(entry.get("link", "")).strip()
        if not title or not link:
            continue
        content_parts = entry.get("content") or []
        body = "\n".join(str(part.get("value", "")) for part in content_parts)
        body = body or str(entry.get("summary", ""))
        body = " ".join(body.split())[:20000]
        external_id = str(entry.get("id") or entry.get("guid") or link)
        published_at = _entry_timestamp(entry)
        content_hash = NormalizedUpdate.fingerprint(
            source.source_id, external_id, link, title, body
        )
        updates.append(
            NormalizedUpdate(
                update_id=NormalizedUpdate.make_id(link),
                source_id=source.source_id,
                vendor=source.vendor,
                technology=source.technology,
                title=title[:500],
                canonical_url=NormalizedUpdate.normalize_url(link),
                published_at=published_at,
                observed_at=datetime.now(timezone.utc),
                content_text=body,
                content_hash=content_hash,
                external_id=external_id,
            )
        )
    return updates

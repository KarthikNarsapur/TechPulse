"""Dispatch configured sources to their adapter implementation."""

from app.adapters.feeds import fetch_feed
from app.adapters.github_releases import fetch_github_releases
from app.models import NormalizedUpdate, SourceConfig, SourceType


def fetch_source(source: SourceConfig) -> list[NormalizedUpdate]:
    if source.source_type in {SourceType.RSS, SourceType.ATOM}:
        return fetch_feed(source)
    if source.source_type == SourceType.GITHUB_RELEASES:
        return fetch_github_releases(source)
    raise NotImplementedError(f"Source type not implemented: {source.source_type}")

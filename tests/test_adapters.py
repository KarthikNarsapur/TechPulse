from datetime import datetime, timezone

from app.adapters.feeds import fetch_feed
from app.adapters.github_releases import fetch_github_releases
from app.models import SourceConfig, SourceType


class FakeResponse:
    def __init__(self, *, content: bytes = b"", payload=None) -> None:
        self.content = content
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


class FakeClient:
    response: FakeResponse

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, *args, **kwargs) -> FakeResponse:
        return self.response


def test_rss_adapter_normalizes_entry_and_drops_tracking(monkeypatch) -> None:
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>Example</title><item>
      <title>Feature launch</title>
      <link>https://example.com/release?utm_source=test#details</link>
      <guid>entry-1</guid>
      <pubDate>Sat, 17 Oct 2026 10:00:00 GMT</pubDate>
      <description>A useful feature</description>
    </item></channel></rss>"""
    FakeClient.response = FakeResponse(content=xml)
    monkeypatch.setattr("app.adapters.feeds.httpx.Client", FakeClient)
    source = SourceConfig(
        source_id="example.rss",
        vendor="example",
        technology="example-tool",
        source_type=SourceType.RSS,
        url="https://example.com/feed.xml",
    )

    results = fetch_feed(source)

    assert len(results) == 1
    assert results[0].title == "Feature launch"
    assert str(results[0].canonical_url) == "https://example.com/release"
    assert results[0].external_id == "entry-1"
    assert results[0].published_at == datetime(2026, 10, 17, 10, 0, tzinfo=timezone.utc)


def test_github_releases_adapter_skips_drafts_and_prereleases(monkeypatch) -> None:
    FakeClient.response = FakeResponse(payload=[
        {
            "id": 1, "html_url": "https://github.com/example/tool/releases/tag/v1.0.0",
            "name": "v1.0.0", "tag_name": "v1.0.0", "body": "Stable",
            "published_at": "2026-10-17T10:00:00Z", "draft": False, "prerelease": False,
        },
        {
            "id": 2, "html_url": "https://github.com/example/tool/releases/tag/v2.0.0-rc.1",
            "name": "RC", "tag_name": "v2.0.0-rc.1", "body": "Release candidate",
            "published_at": "2026-10-17T10:00:00Z", "draft": False, "prerelease": True,
        },
        {
            "id": 3, "html_url": "https://github.com/example/tool/releases/tag/draft",
            "name": "Draft", "tag_name": "draft", "body": "", "draft": True, "prerelease": False,
        },
    ])
    monkeypatch.setattr("app.adapters.github_releases.httpx.Client", FakeClient)
    source = SourceConfig(
        source_id="example.github",
        vendor="example",
        technology="example-tool",
        source_type=SourceType.GITHUB_RELEASES,
        url="https://api.github.com/repos/example/tool/releases",
        repository="example/tool",
    )

    results = fetch_github_releases(source)

    assert len(results) == 1
    assert results[0].title == "v1.0.0"
    assert results[0].external_id == "1"

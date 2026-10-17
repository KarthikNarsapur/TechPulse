from unittest.mock import MagicMock

from app.handlers import ingest
from app.models import NormalizedUpdate, SourceConfig, SourceType


def _source() -> SourceConfig:
    return SourceConfig(
        source_id="aws-release",
        vendor="AWS",
        technology="aws",
        source_type=SourceType.RSS,
        url="https://example.com/feed.xml",
    )


def _update() -> NormalizedUpdate:
    return NormalizedUpdate(
        update_id="update-1",
        source_id="aws-release",
        vendor="AWS",
        technology="aws",
        title="AWS release",
        canonical_url="https://example.com/releases/1",
        content_text="A release announcement",
        content_hash="hash-1",
    )


def test_ingestion_checkpoints_new_changed_and_unchanged(monkeypatch) -> None:
    source = _source()
    update = _update()
    status = MagicMock()
    store = MagicMock()
    store.upsert_revision.return_value = "new"

    monkeypatch.setattr(ingest, "_load_registry", lambda: [source])
    monkeypatch.setattr(ingest, "fetch_source", lambda _source: [update])
    monkeypatch.setattr(ingest, "UpdateStore", lambda: store)
    monkeypatch.setattr(ingest, "PollStatusStore", lambda: status)
    monkeypatch.delenv("TECHPULSE_ANALYSIS_QUEUE_URL", raising=False)

    result = ingest.handler({}, None)

    assert result["sources_checked"] == 1
    assert result["new_updates"] == 1
    status.started.assert_called_once()
    status.succeeded.assert_called_once()
    status.failed.assert_not_called()
    assert status.succeeded.call_args.kwargs["fetched"] == 1
    assert status.succeeded.call_args.kwargs["new_count"] == 1
    assert status.succeeded.call_args.kwargs["changed_count"] == 0

    for outcome in ("changed", "unchanged"):
        status.reset_mock()
        store.upsert_revision.return_value = outcome
        result = ingest.handler({}, None)
        assert result["new_updates"] == 0
        assert result["changed_updates"] == (1 if outcome == "changed" else 0)
        status.started.assert_called_once()
        status.succeeded.assert_called_once()
        status.failed.assert_not_called()


def test_ingestion_records_failure_without_persisting_exception_message(monkeypatch) -> None:
    source = _source()
    status = MagicMock()
    store = MagicMock()
    monkeypatch.setattr(ingest, "_load_registry", lambda: [source])
    monkeypatch.setattr(ingest, "fetch_source", lambda _source: (_ for _ in ()).throw(ValueError("secret query token")))
    monkeypatch.setattr(ingest, "UpdateStore", lambda: store)
    monkeypatch.setattr(ingest, "PollStatusStore", lambda: status)

    result = ingest.handler({}, None)

    assert result["failures"] == []
    status.started.assert_called_once()
    status.failed.assert_called_once()
    assert status.failed.call_args.kwargs["error_type"] == "ValueError"
    assert "secret query token" not in str(status.failed.call_args)

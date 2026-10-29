from datetime import datetime, timezone
from unittest.mock import MagicMock

from botocore.exceptions import ClientError

from app.models import NormalizedUpdate
from app.storage import UpdateStore


def _update(*, content_hash: str, title: str = "Release") -> NormalizedUpdate:
    return NormalizedUpdate(
        update_id="stable-url-id",
        source_id="example.feed",
        vendor="example",
        technology="example-tool",
        title=title,
        canonical_url="https://example.com/releases/1",
        published_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
        observed_at=datetime(2026, 10, 17, tzinfo=timezone.utc),
        content_text=f"Content {content_hash}",
        content_hash=content_hash,
        external_id="release-1",
    )


def _conditional_conflict() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "already exists"}},
        "PutItem",
    )


def test_upsert_revision_inserts_new_update() -> None:
    store = UpdateStore()
    store._table = MagicMock()

    assert store.upsert_revision(_update(content_hash="hash-1")) == "new"
    item = store.table.put_item.call_args.kwargs["Item"]
    assert item["revision"] == 1
    assert item["analysis_status"] == "pending"
    assert item["feed_scope"] == "all"


def test_upsert_revision_marks_identical_content_unchanged() -> None:
    store = UpdateStore()
    store._table = MagicMock()
    store.table.put_item.side_effect = _conditional_conflict()
    store.table.get_item.return_value = {
        "Item": {"update_id": "stable-url-id", "content_hash": "hash-1", "revision": 1}
    }

    assert store.upsert_revision(_update(content_hash="hash-1")) == "unchanged"
    store.table.update_item.assert_called_once()
    assert "last_seen_at" in store.table.update_item.call_args.kwargs["UpdateExpression"]


def test_upsert_revision_marks_material_change_pending() -> None:
    store = UpdateStore()
    store._table = MagicMock()
    store.table.put_item.side_effect = _conditional_conflict()
    store.table.get_item.return_value = {
        "Item": {
            "update_id": "stable-url-id",
            "content_hash": "hash-1",
            "revision": 3,
            "summary": "Previous summary",
            "category": "release",
        }
    }

    assert (
        store.upsert_revision(_update(content_hash="hash-2", title="Updated release")) == "changed"
    )
    call = store.table.update_item.call_args.kwargs
    assert call["ExpressionAttributeValues"][":previous_hash"] == "hash-1"
    assert call["ExpressionAttributeValues"][":revision"] == 4
    assert call["ExpressionAttributeValues"][":status"] == "pending"
    assert "REMOVE #summary, #category, #priority" in call["UpdateExpression"]


def test_upsert_revision_persists_relevance_provider_on_change() -> None:
    store = UpdateStore()
    store._table = MagicMock()
    store.table.put_item.side_effect = _conditional_conflict()
    store.table.get_item.return_value = {
        "Item": {"update_id": "stable-url-id", "content_hash": "hash-1", "revision": 1}
    }
    update = _update(content_hash="hash-2").model_copy(
        update={"relevance_provider": "anthropic", "relevance_model_id": "claude-haiku-5-5"}
    )

    assert store.upsert_revision(update) == "changed"
    kwargs = store.table.update_item.call_args.kwargs
    assert "relevance_provider = :relevance_provider" in kwargs["UpdateExpression"]
    assert kwargs["ExpressionAttributeValues"][":relevance_provider"] == "anthropic"
    assert kwargs["ExpressionAttributeValues"][":relevance_model_id"] == "claude-haiku-5-5"

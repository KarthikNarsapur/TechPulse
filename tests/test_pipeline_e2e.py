from unittest.mock import MagicMock

from app.handlers import analyze as analyze_handler
from app.handlers import ingest as ingest_handler
from app.models import AnalysisResult, SourceConfig, SourceType, UpdateCategory


class FixtureResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class FixtureFeedClient:
    response: FixtureResponse

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def get(self, *args, **kwargs) -> FixtureResponse:
        return self.response


class MemoryUpdateStore:
    def __init__(self) -> None:
        self.items = {}

    def upsert_revision(self, update) -> str:
        self.items[update.update_id] = update.model_dump(mode="json")
        return "new"


class MemoryTable:
    def __init__(self, items=None) -> None:
        self.items = items if items is not None else {}
        self.writes = []

    def get_item(self, *, Key, **kwargs):
        item = self.items.get(tuple(Key.values()))
        return {"Item": item} if item else {}

    def put_item(self, *, Item, **kwargs):
        self.writes.append(Item)
        self.items[(Item["update_id"], Item["analysis_version"])] = Item

    def update_item(
        self,
        *,
        Key,
        UpdateExpression,
        ExpressionAttributeNames,
        ExpressionAttributeValues,
        **kwargs,
    ):
        item = self.items[tuple(Key.values())]
        for placeholder, value in ExpressionAttributeValues.items():
            field = (
                ExpressionAttributeNames.get(placeholder.replace("#", ""))
                if placeholder.startswith("#")
                else None
            )
            if field:
                item[field] = value
        item.update(
            {
                "summary": ExpressionAttributeValues[":summary"],
                "category": ExpressionAttributeValues[":category"],
                "priority": ExpressionAttributeValues[":priority"],
                "analysis_status": ExpressionAttributeValues[":status"],
                "analysis_confidence": ExpressionAttributeValues[":confidence"],
            }
        )
        self.writes.append(item)


def test_fixture_rss_to_persisted_analysis_with_fake_provider(monkeypatch) -> None:
    fixture = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>Fixture</title><item>
      <title>Terraform stable release</title>
      <link>https://example.com/releases/terraform-2</link>
      <guid>terraform-2</guid>
      <pubDate>Sat, 17 Oct 2026 10:00:00 GMT</pubDate>
      <description>Improves plan output and adds a provider feature.</description>
    </item></channel></rss>"""
    FixtureFeedClient.response = FixtureResponse(fixture)
    monkeypatch.setattr("app.adapters.feeds.httpx.Client", FixtureFeedClient)

    source = SourceConfig(
        source_id="fixture.rss",
        vendor="Fixture",
        technology="terraform",
        source_type=SourceType.RSS,
        url="https://example.com/feed.xml",
    )
    updates_store = MemoryUpdateStore()
    poll_status = MagicMock()
    queue = MagicMock()
    queue_messages = []
    queue.send_message.side_effect = lambda **kwargs: (
        queue_messages.append(kwargs) or {"MessageId": "fixture-message"}
    )

    monkeypatch.setattr(ingest_handler, "_load_registry", lambda: [source])
    monkeypatch.setattr(ingest_handler, "UpdateStore", lambda: updates_store)
    monkeypatch.setattr(ingest_handler, "PollStatusStore", lambda: poll_status)
    monkeypatch.setattr(ingest_handler.boto3, "client", lambda *args, **kwargs: queue)
    monkeypatch.setenv("TECHPULSE_ANALYSIS_QUEUE_URL", "https://sqs.example/analysis")
    monkeypatch.setenv("TECHPULSE_MODEL_ID", "fake-provider-model")
    monkeypatch.setenv("TECHPULSE_PROMPT_VERSION", "test-v1")
    monkeypatch.delenv("TECHPULSE_NOTIFICATIONS_QUEUE_URL", raising=False)

    ingestion = ingest_handler.handler({}, None)

    assert ingestion["new_updates"] == 1
    assert poll_status.succeeded.call_count == 1
    assert len(queue_messages) == 1
    analysis_event = {
        "Records": [
            {
                "messageId": "fixture-message",
                "body": queue_messages[0]["MessageBody"],
            }
        ]
    }

    update_table = MemoryTable({(key,): value for key, value in updates_store.items.items()})
    analyses_table = MemoryTable()
    subscriptions_table = MagicMock()
    subscriptions_table.query.return_value = {"Items": []}
    tables = {
        "techpulse-dev-updates": update_table,
        "techpulse-dev-analyses": analyses_table,
        "techpulse-dev-subscriptions": subscriptions_table,
    }
    monkeypatch.setattr(analyze_handler, "_table", lambda name: tables[name])
    fake_result = AnalysisResult(
        summary="Terraform stable release improves plan output.",
        category=UpdateCategory.RELEASE,
        affected_technologies=["terraform"],
        affected_versions=["2.0"],
        evidence=[
            {
                "quote": "Improves plan output",
                "source_url": "https://example.com/releases/terraform-2",
            }
        ],
        confidence=0.95,
        requires_human_review=False,
    )
    provider_calls = []
    monkeypatch.setattr(
        analyze_handler,
        "_invoke_model",
        lambda update, *, model_id, prompt_version: (
            provider_calls.append((update, model_id, prompt_version)) or fake_result
        ),
    )
    analysis = analyze_handler.handler(analysis_event, None)

    assert analysis["batchItemFailures"] == []
    assert len(provider_calls) == 1
    assert provider_calls[0][1:] == ("fake-provider-model", "test-v1")
    stored_update = next(iter(update_table.items.values()))
    assert stored_update["summary"] == fake_result.summary
    assert stored_update["analysis_status"] == "completed"
    assert stored_update["category"] == "release"
    assert analyses_table.writes[0]["result"]["summary"] == fake_result.summary

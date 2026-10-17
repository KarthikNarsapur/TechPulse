import json
from unittest.mock import MagicMock

import pytest

from app.handlers.analyze import _enqueue_subscriber_notifications
from app.models import AnalysisResult, Priority, UpdateCategory


def _analysis() -> AnalysisResult:
    return AnalysisResult(
        summary="A new stable release is available.",
        category=UpdateCategory.RELEASE,
        affected_technologies=["terraform"],
        confidence=0.9,
        requires_human_review=False,
    )


def _update() -> dict:
    return {
        "update_id": "update-123",
        "title": "Terraform 2.0",
        "technology": "terraform",
        "canonical_url": "https://example.com/releases/2",
    }


def test_fanout_queues_only_enabled_valid_subscriptions(monkeypatch) -> None:
    table = MagicMock()
    table.query.return_value = {
        "Items": [
            {"user_id": "user-1", "technology_id": "terraform", "channel": "email", "email": "dev@example.com"},
            {"user_id": "user-2", "technology_id": "terraform", "channel": "slack", "secret_id": "techpulse-dev-notifications-slack"},
            {"user_id": "user-3", "technology_id": "terraform", "channel": "email", "email": "off@example.com", "enabled": False},
            {"user_id": "user-4", "technology_id": "terraform", "channel": "teams", "secret_id": "other-secret"},
            {"user_id": "user-5", "technology_id": "terraform", "channel": "pager", "recipient": "pager@example.com"},
        ]
    }
    queue = MagicMock()
    monkeypatch.setenv("TECHPULSE_NOTIFICATIONS_QUEUE_URL", "https://sqs.example/queue")
    monkeypatch.setattr("app.handlers.analyze._table", lambda name: table)
    monkeypatch.setattr("app.handlers.analyze.boto3.client", lambda *args, **kwargs: queue)

    count = _enqueue_subscriber_notifications(
        _update(), _analysis(), priority=Priority.MEDIUM.value, content_hash="hash-1"
    )

    assert count == 2
    assert table.query.call_args.kwargs["IndexName"] == "technology-index"
    assert queue.send_message.call_count == 2
    messages = [json.loads(call.kwargs["MessageBody"]) for call in queue.send_message.call_args_list]
    assert {message["channel"] for message in messages} == {"email", "slack"}
    assert all(message["delivery_id"] for message in messages)
    assert all("https://example.com/releases/2" in message["body"] for message in messages)


def test_fanout_uses_stable_delivery_id_for_same_revision(monkeypatch) -> None:
    table = MagicMock()
    table.query.return_value = {
        "Items": [
            {"user_id": "user-1", "technology_id": "terraform", "channel": "email", "email": "dev@example.com"}
        ]
    }
    queue = MagicMock()
    monkeypatch.setenv("TECHPULSE_NOTIFICATIONS_QUEUE_URL", "https://sqs.example/queue")
    monkeypatch.setattr("app.handlers.analyze._table", lambda name: table)
    monkeypatch.setattr("app.handlers.analyze.boto3.client", lambda *args, **kwargs: queue)

    for _ in range(2):
        _enqueue_subscriber_notifications(
            _update(), _analysis(), priority=Priority.MEDIUM.value, content_hash="hash-1"
        )

    first = json.loads(queue.send_message.call_args_list[0].kwargs["MessageBody"])["delivery_id"]
    second = json.loads(queue.send_message.call_args_list[1].kwargs["MessageBody"])["delivery_id"]
    assert first == second


def test_fanout_requires_queue_when_a_subscription_matches(monkeypatch) -> None:
    table = MagicMock()
    table.query.return_value = {
        "Items": [
            {"user_id": "user-1", "technology_id": "terraform", "channel": "email", "email": "dev@example.com"}
        ]
    }
    monkeypatch.delenv("TECHPULSE_NOTIFICATIONS_QUEUE_URL", raising=False)
    monkeypatch.setattr("app.handlers.analyze._table", lambda name: table)

    with pytest.raises(RuntimeError, match="TECHPULSE_NOTIFICATIONS_QUEUE_URL"):
        _enqueue_subscriber_notifications(
            _update(), _analysis(), priority=Priority.MEDIUM.value, content_hash="hash-1"
        )


def test_fanout_does_not_require_queue_without_subscribers(monkeypatch) -> None:
    table = MagicMock()
    table.query.return_value = {"Items": []}
    monkeypatch.delenv("TECHPULSE_NOTIFICATIONS_QUEUE_URL", raising=False)
    monkeypatch.setattr("app.handlers.analyze._table", lambda name: table)

    assert _enqueue_subscriber_notifications(
        _update(), _analysis(), priority=Priority.MEDIUM.value, content_hash="hash-1"
    ) == 0

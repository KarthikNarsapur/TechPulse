import json
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from app.handlers.notify import _claim_delivery, _deliver_chat, _resolve_chat_webhook


def _conflict() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
        "PutItem",
    )


def test_claim_delivery_creates_first_claim() -> None:
    table = MagicMock()

    assert _claim_delivery(table, "delivery-1", "claim-a", 1000) == "claimed"
    item = table.put_item.call_args.kwargs["Item"]
    assert item["status"] == "sending"
    assert item["claim_token"] == "claim-a"
    assert item["lease_until"] > 1000


def test_claim_delivery_suppresses_already_sent_delivery() -> None:
    table = MagicMock()
    table.put_item.side_effect = _conflict()
    table.get_item.return_value = {"Item": {"status": "sent", "lease_until": 0}}

    assert _claim_delivery(table, "delivery-1", "claim-b", 1000) == "sent"
    table.update_item.assert_not_called()


def test_claim_delivery_returns_busy_when_lease_is_active() -> None:
    table = MagicMock()
    table.put_item.side_effect = _conflict()
    table.get_item.return_value = {"Item": {"status": "sending", "lease_until": 1100}}

    assert _claim_delivery(table, "delivery-1", "claim-b", 1000) == "busy"
    table.update_item.assert_not_called()


def test_claim_delivery_recovers_expired_lease() -> None:
    table = MagicMock()
    table.put_item.side_effect = _conflict()
    table.get_item.return_value = {
        "Item": {"status": "sending", "lease_until": 900, "claim_token": "old", "attempts": 1}
    }

    assert _claim_delivery(table, "delivery-1", "claim-new", 1000) == "claimed"
    call = table.update_item.call_args.kwargs
    assert call["ExpressionAttributeValues"][":token"] == "claim-new"
    assert call["ExpressionAttributeValues"][":previous_lease"] == 900


def test_chat_delivery_rejects_raw_webhook_url() -> None:
    with pytest.raises(ValueError, match="raw webhook URLs"):
        _deliver_chat(
            {"webhook_url": "https://hooks.slack.com/services/example", "body": "hello"},
            "slack",
        )


def test_chat_secret_rejects_non_techpulse_secret_id(monkeypatch) -> None:
    monkeypatch.setattr("app.handlers.notify.boto3.client", MagicMock())
    with pytest.raises(ValueError, match="TechPulse Secrets Manager"):
        _resolve_chat_webhook("other-app/slack")


def test_chat_secret_accepts_json_secret_for_approved_host(monkeypatch) -> None:
    client = MagicMock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps({"webhook_url": "https://hooks.slack.com/services/example"})
    }
    monkeypatch.setattr("app.handlers.notify.boto3.client", lambda *args, **kwargs: client)

    assert _resolve_chat_webhook("techpulse-dev-notifications-slack") == (
        "https://hooks.slack.com/services/example"
    )


def test_chat_secret_rejects_unapproved_host(monkeypatch) -> None:
    client = MagicMock()
    client.get_secret_value.return_value = {"SecretString": "https://example.com/webhook"}
    monkeypatch.setattr("app.handlers.notify.boto3.client", lambda *args, **kwargs: client)

    with pytest.raises(ValueError, match="non-approved HTTPS host"):
        _resolve_chat_webhook("techpulse-dev-notifications-slack")

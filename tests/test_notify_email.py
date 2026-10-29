import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from app.handlers import notify

CONTEXT = SimpleNamespace(aws_request_id="request-1")
SENDER = "alerts@example.com"
RECIPIENT = "subscriber@example.com"


def _event(**overrides) -> dict:
    payload = {
        "delivery_id": "delivery-1",
        "channel": "email",
        "recipient": RECIPIENT,
        "subject": "[TechPulse HIGH] Kubernetes release",
        "body": "Kubernetes 1.34 is available.",
        **overrides,
    }
    return {"Records": [{"messageId": "message-1", "body": json.dumps(payload)}]}


def _conflict() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException", "Message": "exists"}}, "PutItem"
    )


@pytest.fixture
def ses_env(monkeypatch):
    """Fake deliveries table and SES client; real email is never sent."""
    table = MagicMock()
    ses = MagicMock()
    ses.send_email.return_value = {"MessageId": "ses-message-1"}
    monkeypatch.setenv("TECHPULSE_SES_FROM_ADDRESS", SENDER)
    monkeypatch.setattr(notify, "_deliveries_table", lambda: table)
    monkeypatch.setattr(notify.boto3, "client", lambda service, **kwargs: ses)
    return table, ses


def _last_mark(table) -> dict:
    return table.update_item.call_args.kwargs["ExpressionAttributeValues"]


def test_email_is_sent_and_marked_sent(ses_env) -> None:
    table, ses = ses_env

    result = notify.handler(_event(), CONTEXT)

    assert result == {"batchItemFailures": []}
    kwargs = ses.send_email.call_args.kwargs
    assert kwargs["Source"] == SENDER
    assert kwargs["Destination"] == {"ToAddresses": [RECIPIENT]}
    assert kwargs["Message"]["Subject"]["Data"] == "[TechPulse HIGH] Kubernetes release"
    values = _last_mark(table)
    assert values[":status"] == "sent"
    assert values[":provider_id"] == "ses-message-1"


def test_missing_sender_is_retried_without_calling_ses(ses_env, monkeypatch) -> None:
    table, ses = ses_env
    monkeypatch.setenv("TECHPULSE_SES_FROM_ADDRESS", " ")

    result = notify.handler(_event(), CONTEXT)

    assert result == {"batchItemFailures": [{"itemIdentifier": "message-1"}]}
    ses.send_email.assert_not_called()
    assert _last_mark(table)[":status"] == "failed"
    assert _last_mark(table)[":error"] == "RuntimeError"


def test_missing_recipient_fails_without_calling_ses(ses_env) -> None:
    table, ses = ses_env

    result = notify.handler(_event(recipient=""), CONTEXT)

    assert result == {"batchItemFailures": [{"itemIdentifier": "message-1"}]}
    ses.send_email.assert_not_called()
    assert _last_mark(table)[":error"] == "ValueError"


def test_ses_rejection_is_recorded_without_logging_addresses(ses_env, caplog) -> None:
    table, ses = ses_env
    ses.send_email.side_effect = ClientError(
        {
            "Error": {
                "Code": "MessageRejected",
                "Message": f"Email address is not verified: {RECIPIENT}",
            }
        },
        "SendEmail",
    )

    result = notify.handler(_event(), CONTEXT)

    assert result == {"batchItemFailures": [{"itemIdentifier": "message-1"}]}
    assert _last_mark(table)[":status"] == "failed"
    assert _last_mark(table)[":error"] == "ClientError:MessageRejected"
    assert "MessageRejected" in caplog.text
    assert RECIPIENT not in caplog.text


def test_already_sent_delivery_is_not_sent_again(ses_env) -> None:
    table, ses = ses_env
    table.put_item.side_effect = _conflict()
    table.get_item.return_value = {"Item": {"status": "sent", "lease_until": 0}}

    result = notify.handler(_event(), CONTEXT)

    assert result == {"batchItemFailures": []}
    ses.send_email.assert_not_called()


def test_delivery_held_by_another_worker_is_retried_later(ses_env) -> None:
    table, ses = ses_env
    table.put_item.side_effect = _conflict()
    table.get_item.return_value = {"Item": {"status": "sending", "lease_until": 2**40}}

    result = notify.handler(_event(), CONTEXT)

    assert result == {"batchItemFailures": [{"itemIdentifier": "message-1"}]}
    ses.send_email.assert_not_called()


def test_previously_failed_delivery_is_retried_and_sent(ses_env) -> None:
    table, ses = ses_env
    table.put_item.side_effect = _conflict()
    table.get_item.return_value = {"Item": {"status": "failed", "lease_until": 0, "attempts": 1}}

    result = notify.handler(_event(), CONTEXT)

    assert result == {"batchItemFailures": []}
    ses.send_email.assert_called_once()
    assert _last_mark(table)[":status"] == "sent"

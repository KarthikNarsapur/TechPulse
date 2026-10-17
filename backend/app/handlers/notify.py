"""Notification worker supporting SES, Slack, and Microsoft Teams."""
import json
import logging
import os
from typing import Any

import boto3
import httpx

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _deliver_email(payload: dict[str, Any]) -> str:
    sender = os.getenv("TECHPULSE_SES_FROM_ADDRESS")
    recipient = payload.get("recipient")
    if not sender or not recipient:
        raise ValueError("email notifications require sender and recipient")
    response = boto3.client("ses", region_name=os.getenv("AWS_REGION", "ap-south-1")).send_email(
        Source=sender,
        Destination={"ToAddresses": [str(recipient)]},
        Message={
            "Subject": {"Data": str(payload.get("subject", "TechPulse engineering update"))[:200]},
            "Body": {"Text": {"Data": str(payload.get("body", ""))[:10000]}},
        },
    )
    return str(response["MessageId"])


def _deliver_chat(payload: dict[str, Any], channel: str) -> str:
    # Production jobs should carry a Secrets Manager secret ID, not a user URL.
    # Never accept webhook URLs from the public API; enforce host allowlists.
    webhook_url = str(payload.get("webhook_url") or "")
    if not webhook_url:
        raise ValueError(f"{channel} webhook is not configured")
    parsed = httpx.URL(webhook_url)
    if parsed.scheme != "https" or not parsed.host:
        raise ValueError("chat webhook must use HTTPS")
    with httpx.Client(timeout=10.0, follow_redirects=False) as client:
        response = client.post(webhook_url, json={"text": str(payload.get("body", ""))[:10000]})
        response.raise_for_status()
    return "accepted"


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    for record in event.get("Records", []):
        message_id = str(record.get("messageId", ""))
        try:
            raw = record.get("body", "{}")
            payload = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(payload, dict):
                raise ValueError("message body must be an object")
            delivery_id = str(payload["delivery_id"])
            channel = str(payload.get("channel", "email"))
            if channel == "email":
                provider_id = _deliver_email(payload)
            elif channel in {"slack", "teams"}:
                provider_id = _deliver_chat(payload, channel)
            else:
                raise ValueError(f"unsupported channel: {channel}")
            logger.info(json.dumps({
                "event": "notification_accepted",
                "delivery_id": delivery_id,
                "channel": channel,
                "provider_id": provider_id,
            }))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Invalid notification record %s: %s", message_id, type(exc).__name__)
            failures.append({"itemIdentifier": message_id})
        except Exception:  # noqa: BLE001
            logger.exception("Notification delivery failed for message %s", message_id)
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}

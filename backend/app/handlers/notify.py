"""Notification worker with durable delivery claims and secret-backed chat webhooks.

SQS is at-least-once. A conditional DynamoDB claim suppresses duplicate sends when
the same delivery message is retried after a successful provider response.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any
from urllib.parse import urlsplit

import boto3
import httpx
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

LEASE_SECONDS = 120
ALLOWED_CHAT_HOSTS = (
    "hooks.slack.com",
    "webhook.office.com",
    "webhook.office365.com",
    "logic.azure.com",
)


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


def _resolve_chat_webhook(secret_id: str) -> str:
    """Read a webhook only from an approved Secrets Manager secret."""
    if not secret_id or not secret_id.startswith("techpulse-"):
        raise ValueError("chat notifications require a TechPulse Secrets Manager secret ID")
    secret = boto3.client(
        "secretsmanager", region_name=os.getenv("AWS_REGION", "ap-south-1")
    ).get_secret_value(SecretId=secret_id)
    value = secret.get("SecretString")
    if not isinstance(value, str) or not value:
        raise ValueError("chat webhook secret must contain a SecretString")
    try:
        decoded = json.loads(value)
        webhook_url = str(decoded.get("webhook_url", "")) if isinstance(decoded, dict) else value
    except json.JSONDecodeError:
        webhook_url = value
    parsed = urlsplit(webhook_url)
    host = (parsed.hostname or "").lower()
    allowed = any(host == suffix or host.endswith("." + suffix) for suffix in ALLOWED_CHAT_HOSTS)
    if parsed.scheme != "https" or not allowed or parsed.username or parsed.password:
        raise ValueError("chat webhook secret contains a non-approved HTTPS host")
    return webhook_url


def _deliver_chat(payload: dict[str, Any], channel: str) -> str:
    # Raw webhook URLs are intentionally rejected. The queue carries a secret ID.
    if payload.get("webhook_url"):
        raise ValueError("raw webhook URLs are not accepted; use secret_id")
    webhook_url = _resolve_chat_webhook(str(payload.get("secret_id") or ""))
    with httpx.Client(timeout=10.0, follow_redirects=False) as client:
        response = client.post(webhook_url, json={"text": str(payload.get("body", ""))[:10000]})
        response.raise_for_status()
    return "accepted"


def _deliveries_table() -> Any:
    table_name = os.getenv("TECHPULSE_DELIVERIES_TABLE")
    if not table_name:
        raise RuntimeError("TECHPULSE_DELIVERIES_TABLE must be configured")
    return boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "ap-south-1")).Table(
        table_name
    )


def _claim_delivery(table: Any, delivery_id: str, claim_token: str, now: int) -> str:
    """Return claimed, sent, or busy. Claims are recoverable after a worker crash."""
    lease_until = now + LEASE_SECONDS
    try:
        table.put_item(
            Item={
                "delivery_id": delivery_id,
                "status": "sending",
                "claim_token": claim_token,
                "lease_until": lease_until,
                "attempts": 1,
                "created_at": now,
                "updated_at": now,
            },
            ConditionExpression="attribute_not_exists(delivery_id)",
        )
        return "claimed"
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise

    current = table.get_item(Key={"delivery_id": delivery_id}, ConsistentRead=True).get("Item")
    if not current:
        # A deletion/race can occur between conditional write and consistent read.
        return "busy"
    if current.get("status") == "sent":
        return "sent"
    if int(current.get("lease_until", 0)) > now:
        return "busy"

    try:
        table.update_item(
            Key={"delivery_id": delivery_id},
            UpdateExpression=(
                "SET #status = :sending, claim_token = :token, lease_until = :lease, "
                "updated_at = :now, attempts = if_not_exists(attempts, :zero) + :one"
            ),
            ConditionExpression="lease_until = :previous_lease AND #status = :previous_status",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":sending": "sending",
                ":token": claim_token,
                ":lease": lease_until,
                ":now": now,
                ":zero": 0,
                ":one": 1,
                ":previous_lease": current.get("lease_until", 0),
                ":previous_status": current.get("status", "failed"),
            },
        )
        return "claimed"
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return "busy"
        raise


def _mark_delivery(
    table: Any,
    delivery_id: str,
    claim_token: str,
    *,
    status: str,
    now: int,
    provider_id: str = "",
    error: str = "",
) -> None:
    values: dict[str, Any] = {
        ":status": status,
        ":now": now,
        ":token": claim_token,
        ":zero": 0,
    }
    expression = "SET #status = :status, updated_at = :now, lease_until = :zero"
    names = {"#status": "status"}
    if provider_id:
        expression += ", provider_id = :provider_id"
        values[":provider_id"] = provider_id
    if error:
        expression += ", last_error = :error"
        values[":error"] = error[:300]
    table.update_item(
        Key={"delivery_id": delivery_id},
        UpdateExpression=expression,
        ConditionExpression="claim_token = :token",
        ExpressionAttributeNames=names,
        ExpressionAttributeValues=values,
    )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    failures: list[dict[str, str]] = []
    table = _deliveries_table()
    for record in event.get("Records", []):
        message_id = str(record.get("messageId", ""))
        claim_token = str(getattr(context, "aws_request_id", "") or uuid.uuid4().hex)
        delivery_id = ""
        claimed = False
        try:
            raw = record.get("body", "{}")
            payload = json.loads(raw) if isinstance(raw, str) else raw
            if not isinstance(payload, dict):
                raise ValueError("message body must be an object")
            delivery_id = str(payload.get("delivery_id", "")).strip()
            if not delivery_id:
                raise ValueError("delivery_id is required")

            now = int(time.time())
            claim = _claim_delivery(table, delivery_id, claim_token, now)
            if claim == "sent":
                logger.info(
                    json.dumps(
                        {"event": "notification_duplicate_suppressed", "delivery_id": delivery_id}
                    )
                )
                continue
            if claim != "claimed":
                # Retry after the current worker's lease expires; don't drop the job.
                failures.append({"itemIdentifier": message_id})
                continue
            claimed = True

            channel = str(payload.get("channel", "email"))
            if channel == "email":
                provider_id = _deliver_email(payload)
            elif channel in {"slack", "teams"}:
                provider_id = _deliver_chat(payload, channel)
            else:
                raise ValueError(f"unsupported channel: {channel}")

            _mark_delivery(
                table,
                delivery_id,
                claim_token,
                status="sent",
                now=int(time.time()),
                provider_id=provider_id,
            )
            logger.info(
                json.dumps(
                    {
                        "event": "notification_accepted",
                        "delivery_id": delivery_id,
                        "channel": channel,
                        "provider_id": provider_id,
                    }
                )
            )
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Invalid notification record %s: %s", message_id, type(exc).__name__)
            if claimed and delivery_id:
                try:
                    _mark_delivery(
                        table,
                        delivery_id,
                        claim_token,
                        status="failed",
                        now=int(time.time()),
                        error=type(exc).__name__,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Unable to persist failed delivery state")
            failures.append({"itemIdentifier": message_id})
        except Exception as exc:  # noqa: BLE001
            logger.exception("Notification delivery failed for message %s", message_id)
            if claimed and delivery_id:
                try:
                    _mark_delivery(
                        table,
                        delivery_id,
                        claim_token,
                        status="failed",
                        now=int(time.time()),
                        error=type(exc).__name__,
                    )
                except Exception:  # noqa: BLE001
                    logger.exception("Unable to persist failed delivery state")
            failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}

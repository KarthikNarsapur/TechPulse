"""Notification Lambda handler placeholder with partial batch failure support."""
import json
import logging
from typing import Any

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Validate notification job contracts without sending messages yet."""
    failures = []
    accepted = 0
    for record in event.get("Records", []):
        try:
            body = record.get("body", "{}")
            payload = json.loads(body) if isinstance(body, str) else body
            if not isinstance(payload, dict) or not payload.get("delivery_id"):
                raise ValueError("message requires delivery_id")
            if payload.get("channel") not in {"email", "slack", "teams"}:
                raise ValueError("unsupported channel")
            accepted += 1
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            failures.append({"itemIdentifier": str(record.get("messageId", ""))})
            logger.warning("Invalid notification job: %s", type(exc).__name__)
    return {"accepted": accepted, "batchItemFailures": failures}

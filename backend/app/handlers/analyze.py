"""Analysis Lambda handler.

AI extraction/classification/summary uses one structured call per new content
version. Priority and deadline logic remain deterministic.
"""
import hashlib
import json
import logging
import os
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from app.ai_provider import configured_analysis_provider
from app.models import AnalysisResult, UpdateCategory, deterministic_priority

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _table(name: str) -> Any:
    return boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "ap-south-1")).Table(name)


def _cache_key(content_hash: str, model_id: str, prompt_version: str) -> str:
    return hashlib.sha256(f"{content_hash}:{model_id}:{prompt_version}".encode()).hexdigest()


def _invoke_model(update: dict[str, Any], *, model_id: str, prompt_version: str) -> AnalysisResult:
    """Compatibility wrapper around the injectable provider interface."""
    provider = configured_analysis_provider(model_id, prompt_version)
    if provider is None:
        raise ValueError("A model ID is required for Bedrock analysis")
    return provider.analyze(update)

def _enqueue_subscriber_notifications(
    update: dict[str, Any],
    result: AnalysisResult,
    *,
    priority: str,
    content_hash: str,
) -> int:
    """Queue one stable delivery per enabled technology subscription."""
    table_name = os.getenv("TECHPULSE_SUBSCRIPTIONS_TABLE", "techpulse-dev-subscriptions")
    subscriptions = _table(table_name)
    technology = str(update.get("technology", ""))
    index_name = os.getenv("TECHPULSE_SUBSCRIPTION_TECH_INDEX", "technology-index")
    query_args: dict[str, Any] = {
        "IndexName": index_name,
        "KeyConditionExpression": Key("technology_id").eq(technology),
    }
    matches: list[dict[str, Any]] = []
    while True:
        response = subscriptions.query(**query_args)
        matches.extend(response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            break
        query_args["ExclusiveStartKey"] = last_key

    eligible: list[dict[str, Any]] = []
    for subscription in matches:
        if subscription.get("enabled", True) is False:
            continue
        channel = str(subscription.get("channel", "email")).lower()
        if channel == "email":
            recipient = str(subscription.get("email") or subscription.get("recipient") or "").strip()
            if not recipient:
                logger.warning("Skipping email subscription without recipient for technology=%s", technology)
                continue
            destination = {"recipient": recipient}
        elif channel in {"slack", "teams"}:
            secret_id = str(subscription.get("secret_id") or "").strip()
            if not secret_id.startswith("techpulse-"):
                logger.warning("Skipping chat subscription without a TechPulse secret reference")
                continue
            destination = {"secret_id": secret_id}
        else:
            logger.warning("Skipping unsupported notification channel=%s", channel)
            continue

        user_id = str(subscription.get("user_id") or destination.get("recipient") or destination.get("secret_id"))
        delivery_id = hashlib.sha256(
            f"{update['update_id']}:{content_hash}:{user_id}:{channel}".encode("utf-8")
        ).hexdigest()
        eligible.append({
            "delivery_id": delivery_id,
            "channel": channel,
            **destination,
            "subject": f"[TechPulse {priority.upper()}] {str(update.get('title', 'Engineering update'))[:160]}",
            "body": (
                f"{str(update.get('title', 'Engineering update'))[:500]}\n\n"
                f"{result.summary[:3000]}\n\n"
                f"Technology: {technology}\nPriority: {priority}\n"
                f"Source: {update.get('canonical_url', '')}"
            ),
            "update_id": str(update.get("update_id", "")),
            "content_hash": content_hash,
        })

    if not eligible:
        return 0
    queue_url = os.getenv("TECHPULSE_NOTIFICATIONS_QUEUE_URL")
    if not queue_url:
        raise RuntimeError("TECHPULSE_NOTIFICATIONS_QUEUE_URL must be configured when subscriptions match")

    queue = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "ap-south-1"))
    for payload in eligible:
        queue.send_message(QueueUrl=queue_url, MessageBody=json.dumps(payload))
    logger.info(json.dumps({
        "event": "subscriber_notifications_enqueued",
        "technology": technology,
        "count": len(eligible),
        "content_hash": content_hash,
    }))
    return len(eligible)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    updates = _table(os.getenv("TECHPULSE_UPDATES_TABLE", "techpulse-dev-updates"))
    analyses = _table(os.getenv("TECHPULSE_ANALYSES_TABLE", "techpulse-dev-analyses"))
    failures: list[dict[str, str]] = []

    for record in event.get("Records", []):
        message_id = str(record.get("messageId", ""))
        try:
            body = record.get("body", "{}")
            payload = json.loads(body) if isinstance(body, str) else body
            if not isinstance(payload, dict):
                raise ValueError("message body must be an object")
            update_id = str(payload["update_id"])
            content_hash = str(payload["content_hash"])
            update = updates.get_item(Key={"update_id": update_id}, ConsistentRead=True).get("Item")
            if not update:
                raise ValueError(f"Update not found: {update_id}")

            model_id = os.getenv("TECHPULSE_MODEL_ID", "")
            prompt_version = os.getenv("TECHPULSE_PROMPT_VERSION", "v1")
            cache_key = _cache_key(content_hash, model_id or "disabled", prompt_version)
            cached = analyses.get_item(
                Key={"update_id": update_id, "analysis_version": cache_key},
                ConsistentRead=True,
            ).get("Item")

            if cached:
                result = AnalysisResult.model_validate(cached["result"])
            elif model_id:
                result = _invoke_model(update, model_id=model_id, prompt_version=prompt_version)
                analyses.put_item(Item={
                    "update_id": update_id,
                    "analysis_version": cache_key,
                    "content_hash": content_hash,
                    "model_id": model_id,
                    "prompt_version": prompt_version,
                    "result": result.model_dump(mode="json"),
                })
            else:
                # Safe degraded mode: do not make up a summary when AI is disabled.
                result = AnalysisResult(
                    summary="AI analysis is not configured. Review the official announcement.",
                    category=UpdateCategory.OTHER,
                    affected_technologies=[str(update.get("technology", "unknown"))],
                    evidence=[{"source_url": update.get("canonical_url")}],
                    confidence=0.0,
                    requires_human_review=True,
                )

            priority = deterministic_priority(
                category=result.category,
                evidence_confidence=result.confidence,
                confirmed_exposure=False,
                urgent_deadline=False,
            )
            updates.update_item(
                Key={"update_id": update_id},
                UpdateExpression="SET #summary = :summary, #category = :category, #priority = :priority, analysis_status = :status, analysis_confidence = :confidence",
                ExpressionAttributeNames={
                    "#summary": "summary",
                    "#category": "category",
                    "#priority": "priority",
                },
                ExpressionAttributeValues={
                    ":summary": result.summary,
                    ":category": result.category.value,
                    ":priority": priority.value,
                    ":status": "completed" if model_id else "analysis_disabled",
                    ":confidence": result.confidence,
                },
            )
            if model_id:
                _enqueue_subscriber_notifications(
                    update,
                    result,
                    priority=priority.value,
                    content_hash=content_hash,
                )
            logger.info(json.dumps({
                "event": "analysis_completed",
                "update_id": update_id,
                "category": result.category.value,
                "priority": priority.value,
                "requires_human_review": result.requires_human_review,
            }))
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            logger.warning("Invalid analysis record %s: %s", message_id, type(exc).__name__)
            failures.append({"itemIdentifier": message_id})
        except ClientError:
            logger.exception("AWS service error analyzing message %s", message_id)
            failures.append({"itemIdentifier": message_id})
        except Exception:  # noqa: BLE001
            logger.exception("Analysis failed for message %s", message_id)
            failures.append({"itemIdentifier": message_id})

    return {"batchItemFailures": failures}

"""Dispatcher and SQS-triggered ingestion Lambda."""
import json
import logging
import os
from typing import Any

import boto3

from app.adapters.registry import fetch_source
from app.models import SourceConfig
from app.source_registry import load_sources
from app.storage import SourceStore, UpdateStore

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _queue_url() -> str | None:
    return os.getenv("TECHPULSE_ANALYSIS_QUEUE_URL")


def _load_registry() -> list[SourceConfig]:
    """Prefer persisted source configuration; YAML is the local bootstrap fallback."""
    table_name = os.getenv("TECHPULSE_SOURCES_TABLE")
    if table_name:
        try:
            persisted = [SourceConfig.model_validate(item) for item in SourceStore(table_name).all_enabled()]
            if persisted:
                return persisted
        except Exception:  # noqa: BLE001
            logger.exception("Unable to load persisted registry; using bundled registry")
    return load_sources()


def _enqueue_analysis(update_id: str, content_hash: str, source_id: str) -> None:
    queue_url = _queue_url()
    if not queue_url:
        return
    boto3.client("sqs", region_name=os.getenv("AWS_REGION", "ap-south-1")).send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            "update_id": update_id,
            "content_hash": content_hash,
            "source_id": source_id,
        }),
    )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process EventBridge source requests or SQS source jobs."""
    is_sqs = bool(event.get("Records"))
    source_jobs: dict[str, str] = {}
    if is_sqs:
        for record in event.get("Records", []):
            body = record.get("body", "{}")
            try:
                payload = json.loads(body) if isinstance(body, str) else body
            except json.JSONDecodeError:
                source_jobs[str(record.get("messageId", ""))] = ""
                continue
            if isinstance(payload, dict) and payload.get("source_id"):
                source_jobs[str(record.get("messageId", payload["source_id"]))] = str(payload["source_id"])
    elif event.get("source_id"):
        source_jobs["direct"] = str(event["source_id"])

    registry = _load_registry()
    by_id = {source.source_id: source for source in registry}
    selected = registry if not is_sqs and not source_jobs else [
        by_id[source_id] for source_id in source_jobs.values() if source_id in by_id
    ]

    store = UpdateStore()
    failed_ids: set[str] = set()
    source_count = 0
    new_count = 0
    for source in selected:
        source_count += 1
        try:
            updates = fetch_source(source)
            for update in updates:
                if store.put_update_if_new(update):
                    new_count += 1
                    _enqueue_analysis(update.update_id, update.content_hash, update.source_id)
            logger.info(json.dumps({
                "event": "source_poll_succeeded",
                "source_id": source.source_id,
                "fetched": len(updates),
            }))
        except Exception as exc:  # noqa: BLE001 - queue retry is responsible for transient failures
            logger.exception("Source poll failed: %s", source.source_id)
            for message_id, source_id in source_jobs.items():
                if source_id == source.source_id:
                    failed_ids.add(message_id)

    failures = [{"itemIdentifier": message_id} for message_id in failed_ids]
    if is_sqs:
        return {"batchItemFailures": failures, "sources_checked": source_count, "new_updates": new_count}
    return {"sources_checked": source_count, "new_updates": new_count, "failures": failures}

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
    """Prefer source configuration persisted in DynamoDB; YAML is a local bootstrap fallback."""
    table_name = os.getenv("TECHPULSE_SOURCES_TABLE")
    if table_name:
        try:
            return [SourceConfig.model_validate(item) for item in SourceStore(table_name).all_enabled()]
        except Exception:  # noqa: BLE001 - local fallback is explicitly logged
            logger.exception("Unable to load persisted source registry; using bundled registry fallback")
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
    """Handle an EventBridge poll request or SQS source job."""
    is_sqs = bool(event.get("Records"))
    requested_ids: set[str] = set()
    if is_sqs:
        for record in event.get("Records", []):
            body = record.get("body", "{}")
            try:
                payload = json.loads(body) if isinstance(body, str) else body
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and payload.get("source_id"):
                requested_ids.add(str(payload["source_id"]))
    elif event.get("source_id"):
        requested_ids.add(str(event["source_id"]))

    sources = _load_registry()
    if requested_ids:
        sources = [source for source in sources if source.source_id in requested_ids]

    store = UpdateStore()
    failures: list[dict[str, str]] = []
    source_count = 0
    new_count = 0
    for source in sources:
        source_count += 1
        try:
            updates = fetch_source(source)
            for update in updates:
                is_new = store.put_update_if_new(update)
                if is_new:
                    new_count += 1
                    _enqueue_analysis(update.update_id, update.content_hash, update.source_id)
            logger.info(json.dumps({
                "event": "source_poll_succeeded",
                "source_id": source.source_id,
                "fetched": len(updates),
                "new": sum(1 for item in updates if store.get(item.update_id) is not None),
            }))
        except Exception as exc:  # noqa: BLE001 - source failures are isolated
            logger.exception("Source poll failed: %s", source.source_id)
            failures.append({"itemIdentifier": source.source_id, "error": type(exc).__name__})

    # SQS event source mappings use partial batch response semantics.
    if is_sqs:
        return {"batchItemFailures": failures, "sources_checked": source_count, "new_updates": new_count}
    return {"sources_checked": source_count, "new_updates": new_count, "failures": failures}

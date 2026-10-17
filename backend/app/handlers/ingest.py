"""Dispatcher and SQS-triggered ingestion Lambda."""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

import boto3

from app.adapters.registry import fetch_source
from app.models import SourceConfig
from app.source_registry import load_sources
from app.storage import PollStatusStore, SourceStore, UpdateStore

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _load_registry() -> list[SourceConfig]:
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
    queue_url = os.getenv("TECHPULSE_ANALYSIS_QUEUE_URL")
    if not queue_url:
        logger.warning("Analysis queue URL missing; update stored without analysis enqueue")
        return
    boto3.client("sqs", region_name=os.getenv("AWS_REGION", "ap-south-1")).send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            "update_id": update_id,
            "content_hash": content_hash,
            "source_id": source_id,
        }),
        MessageDeduplicationId=f"{update_id}:{content_hash}",
        MessageGroupId=source_id,
    ) if os.getenv("TECHPULSE_ANALYSIS_FIFO_QUEUE", "false").lower() == "true" else boto3.client(
        "sqs", region_name=os.getenv("AWS_REGION", "ap-south-1")
    ).send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps({
            "update_id": update_id,
            "content_hash": content_hash,
            "source_id": source_id,
        }),
    )


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    is_sqs = bool(event.get("Records"))
    source_jobs: dict[str, str] = {}

    if is_sqs:
        for record in event.get("Records", []):
            message_id = str(record.get("messageId", ""))
            body = record.get("body", "{}")
            try:
                payload = json.loads(body) if isinstance(body, str) else body
            except json.JSONDecodeError:
                source_jobs[message_id] = ""
                continue
            if isinstance(payload, dict) and payload.get("source_id"):
                source_jobs[message_id] = str(payload["source_id"])
            else:
                source_jobs[message_id] = ""
    elif event.get("source_id"):
        source_jobs["direct"] = str(event["source_id"])

    registry = _load_registry()
    by_id = {source.source_id: source for source in registry}
    selected = registry if not is_sqs and not source_jobs else [
        by_id[source_id] for source_id in source_jobs.values() if source_id in by_id
    ]
    failed_ids: set[str] = {
        message_id for message_id, source_id in source_jobs.items() if not source_id or source_id not in by_id
    }

    store = UpdateStore()
    sources_processed = 0
    new_count = 0
    changed_count = 0
    failed_sources: list[str] = []
    for source in selected:
        sources_processed += 1
        related_message_ids = [
            message_id for message_id, source_id in source_jobs.items() if source_id == source.source_id
        ]
        try:
            status_store = PollStatusStore()
            status_store.started(source.source_id, started_at=datetime.now(timezone.utc).isoformat())
            updates = fetch_source(source)
            source_new = 0
            source_changed = 0
            for update in updates:
                outcome = store.upsert_revision(update)
                if outcome == "new":
                    source_new += 1
                    _enqueue_analysis(update.update_id, update.content_hash, update.source_id)
                elif outcome == "changed":
                    source_changed += 1
                    _enqueue_analysis(update.update_id, update.content_hash, update.source_id)
            new_count += source_new
            changed_count += source_changed
            status_store.succeeded(
                source.source_id,
                completed_at=datetime.now(timezone.utc).isoformat(),
                fetched=len(updates),
                new_count=source_new,
                changed_count=source_changed,
            )
            logger.info(json.dumps({
                "event": "source_poll_succeeded",
                "source_id": source.source_id,
                "fetched": len(updates),
                "new": source_new,
                "changed": source_changed,
                "duration_status": "checkpointed",
            }))
        except Exception as exc:  # noqa: BLE001 - let SQS retry transient source failure
            logger.exception("Source poll failed: %s", source.source_id)
            try:
                PollStatusStore().failed(
                    source.source_id,
                    failed_at=datetime.now(timezone.utc).isoformat(),
                    error_type=type(exc).__name__,
                )
            except Exception:  # noqa: BLE001 - preserve the original poll failure
                logger.exception("Unable to persist poll failure status: %s", source.source_id)
            failed_sources.append(source.source_id)
            failed_ids.update(related_message_ids)

    failures = [{"itemIdentifier": message_id} for message_id in sorted(failed_ids)]
    if is_sqs:
        return {
            "batchItemFailures": failures,
            "sources_checked": sources_processed,
            "new_updates": new_count,
            "changed_updates": changed_count,
        }
    return {
        "sources_checked": sources_processed,
        "new_updates": new_count,
        "changed_updates": changed_count,
        "failed_sources": failed_sources,
        "failures": failures,
    }

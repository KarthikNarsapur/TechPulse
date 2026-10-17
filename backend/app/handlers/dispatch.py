"""EventBridge dispatcher: enqueue one SQS message per enabled source."""
import json
import logging
import os
from typing import Any

import boto3

from app.source_registry import load_sources
from app.storage import SourceStore

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _sources() -> list[dict[str, Any]]:
    table = os.getenv("TECHPULSE_SOURCES_TABLE")
    if table:
        items = SourceStore(table).all_enabled()
        if items:
            return items
    return [source.model_dump(mode="json") for source in load_sources()]


def handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    queue_url = os.environ.get("TECHPULSE_INGESTION_QUEUE_URL")
    if not queue_url:
        raise RuntimeError("TECHPULSE_INGESTION_QUEUE_URL must be configured")
    sqs = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "ap-south-1"))
    enqueued = 0
    for source in _sources():
        if not source.get("enabled", True):
            continue
        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"source_id": source["source_id"]}),
            MessageGroupId=source["source_id"] if queue_url.endswith(".fifo") else None,
        ) if queue_url.endswith(".fifo") else sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"source_id": source["source_id"]}),
        )
        enqueued += 1
    logger.info(json.dumps({"event": "poll_dispatch_complete", "sources_enqueued": enqueued}))
    return {"sources_enqueued": enqueued}

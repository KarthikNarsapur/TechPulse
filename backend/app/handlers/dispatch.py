"""EventBridge dispatcher: enqueue one SQS job per enabled source."""
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
    # Treat the checked-in registry as authoritative for shipped sources, while
    # retaining enabled custom entries stored in DynamoDB.
    sources = {source.source_id: source.model_dump(mode="json") for source in load_sources()}
    table = os.getenv("TECHPULSE_SOURCES_TABLE")
    if table:
        try:
            for stored in SourceStore(table).all_enabled():
                sources.setdefault(str(stored["source_id"]), stored)
        except Exception:  # noqa: BLE001
            logger.exception("Unable to load persisted custom sources")
    return list(sources.values())


def handler(event: dict[str, Any], context: Any) -> dict[str, int]:
    queue_url = os.environ.get("TECHPULSE_INGESTION_QUEUE_URL")
    if not queue_url:
        raise RuntimeError("TECHPULSE_INGESTION_QUEUE_URL must be configured")

    client = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "ap-south-1"))
    enqueued = 0
    for source in _sources():
        if source.get("enabled", True):
            client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps({"source_id": source["source_id"]}),
            )
            enqueued += 1

    logger.info(json.dumps({"event": "poll_dispatch_complete", "sources_enqueued": enqueued}))
    return {"sources_enqueued": enqueued}

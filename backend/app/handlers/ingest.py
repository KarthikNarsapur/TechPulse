"""SQS-triggered ingestion Lambda."""
import json
import logging
from typing import Any

from app.adapters.registry import fetch_source
from app.models import SourceConfig
from app.source_registry import load_sources

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Process one or more source jobs.

    EventBridge can enqueue {source_id}; for manual testing, an empty event
    polls all enabled registry entries. Persistence and queue fan-out are
    added in the next implementation increment.
    """
    requested_ids = {
        str(record.get("body", record).get("source_id"))
        for record in event.get("Records", [])
        if isinstance(record, dict) and isinstance(record.get("body", record), dict)
    }
    if event.get("source_id"):
        requested_ids.add(str(event["source_id"]))

    sources = load_sources()
    if requested_ids:
        sources = [source for source in sources if source.source_id in requested_ids]

    processed = 0
    failures: list[dict[str, str]] = []
    for source in sources:
        try:
            updates = fetch_source(source)
            processed += len(updates)
            logger.info(
                json.dumps({
                    "event": "source_fetched",
                    "source_id": source.source_id,
                    "updates_count": len(updates),
                })
            )
        except Exception as exc:  # noqa: BLE001 - isolate failure per source
            logger.exception("Source fetch failed: %s", source.source_id)
            failures.append({"source_id": source.source_id, "error": type(exc).__name__})

    return {"sources_checked": len(sources), "updates_fetched": processed, "failures": failures}

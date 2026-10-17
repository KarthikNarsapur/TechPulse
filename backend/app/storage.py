"""DynamoDB persistence helpers with explicit conditional-write semantics."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import ClientError

from app.models import NormalizedUpdate


class UpdateStore:
    def __init__(self, table_name: str | None = None, *, region_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("TECHPULSE_UPDATES_TABLE", "techpulse-dev-updates")
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self._table: Any | None = None

    @property
    def table(self) -> Any:
        if self._table is None:
            self._table = boto3.resource("dynamodb", region_name=self.region_name).Table(self.table_name)
        return self._table

    def get(self, update_id: str) -> dict[str, Any] | None:
        result = self.table.get_item(Key={"update_id": update_id}, ConsistentRead=True)
        return result.get("Item")

    def put_if_absent(self, item: dict[str, Any]) -> bool:
        """Atomically insert a new canonical update."""
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(update_id)")
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

    def put_update_if_new(self, update: NormalizedUpdate) -> bool:
        """Persist a new update; an existing URL is not overwritten."""
        item = update.model_dump(mode="json")
        item["published_key"] = (
            update.published_at.astimezone(timezone.utc).isoformat()
            if update.published_at
            else update.observed_at.astimezone(timezone.utc).isoformat()
        ) + "#" + update.update_id
        item["first_seen_at"] = datetime.now(timezone.utc).isoformat()
        item["analysis_status"] = "pending"
        item["feed_scope"] = "all"
        return self.put_if_absent(item)

    def upsert_revision(self, update: NormalizedUpdate) -> str:
        """Create or update a canonical record and identify whether analysis is needed.

        Returns `new`, `changed`, or `unchanged`. Canonical identity is based on
        URL while `content_hash` tracks material content revisions. Conditional
        writes make concurrent duplicate polls safe.
        """
        now = datetime.now(timezone.utc).isoformat()
        item = update.model_dump(mode="json")
        item["published_key"] = (
            update.published_at.astimezone(timezone.utc).isoformat()
            if update.published_at
            else update.observed_at.astimezone(timezone.utc).isoformat()
        ) + "#" + update.update_id
        item["feed_scope"] = "all"

        try:
            item["first_seen_at"] = now
            item["last_seen_at"] = now
            item["revision"] = 1
            item["analysis_status"] = "pending"
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(update_id)")
            return "new"
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise

        existing = self.get(update.update_id)
        if not existing:
            # A record may have been deleted between the failed conditional write
            # and the consistent read. Retry once using the same conditional insert.
            item["first_seen_at"] = now
            item["last_seen_at"] = now
            item["revision"] = 1
            item["analysis_status"] = "pending"
            try:
                self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(update_id)")
                return "new"
            except ClientError as exc:
                if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                    existing = self.get(update.update_id)
                else:
                    raise
        if not existing:
            raise RuntimeError("Unable to read canonical update after conditional conflict")

        if existing.get("content_hash") == update.content_hash:
            self.table.update_item(
                Key={"update_id": update.update_id},
                UpdateExpression="SET last_seen_at = :seen",
                ExpressionAttributeValues={":seen": now},
            )
            return "unchanged"

        # Update only if the previously observed hash still matches. If another
        # poll wins the race, the conditional conflict is safe to retry next poll.
        try:
            self.table.update_item(
                Key={"update_id": update.update_id},
                UpdateExpression=(
                    "SET #title = :title, canonical_url = :url, published_at = :published, "
                    "observed_at = :observed, content_text = :content, content_hash = :hash, "
                    "source_id = :source, vendor = :vendor, technology = :technology, "
                    "external_id = :external_id, last_seen_at = :seen, revision = :revision, "
                    "analysis_status = :status REMOVE #summary, #category, #priority, analysis_confidence"
                ),
                ConditionExpression="content_hash = :previous_hash",
                ExpressionAttributeNames={
                    "#title": "title",
                    "#summary": "summary",
                    "#category": "category",
                    "#priority": "priority",
                },
                ExpressionAttributeValues={
                    ":title": update.title,
                    ":url": str(update.canonical_url),
                    ":published": update.published_at.isoformat() if update.published_at else None,
                    ":observed": update.observed_at.isoformat(),
                    ":content": update.content_text,
                    ":hash": update.content_hash,
                    ":source": update.source_id,
                    ":vendor": update.vendor,
                    ":technology": update.technology,
                    ":external_id": update.external_id or "",
                    ":seen": now,
                    ":revision": int(existing.get("revision", 1)) + 1,
                    ":status": "pending",
                    ":previous_hash": existing.get("content_hash"),
                },
            )
            return "changed"
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return "unchanged"
            raise

    def query_all(
        self,
        *,
        limit: int = 20,
        exclusive_start_key: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Query the shared feed without scanning the canonical table."""
        kwargs: dict[str, Any] = {
            "IndexName": os.getenv("TECHPULSE_ALL_UPDATES_INDEX", "published-index"),
            "KeyConditionExpression": Key("feed_scope").eq("all"),
            "ScanIndexForward": False,
            "Limit": max(1, min(limit, 100)),
        }
        if exclusive_start_key:
            kwargs["ExclusiveStartKey"] = exclusive_start_key
        result = self.table.query(**kwargs)
        return {"items": result.get("Items", []), "last_evaluated_key": result.get("LastEvaluatedKey")}

    def query_by_technology(
        self,
        technology: str,
        *,
        limit: int = 20,
        exclusive_start_key: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "IndexName": os.getenv("TECHPULSE_UPDATE_INDEX", "technology-published-index"),
            "KeyConditionExpression": Key("technology").eq(technology),
            "ScanIndexForward": False,
            "Limit": max(1, min(limit, 100)),
        }
        if exclusive_start_key:
            kwargs["ExclusiveStartKey"] = exclusive_start_key
        result = self.table.query(**kwargs)
        return {"items": result.get("Items", []), "last_evaluated_key": result.get("LastEvaluatedKey")}


class SourceStore:
    def __init__(self, table_name: str | None = None, *, region_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("TECHPULSE_SOURCES_TABLE", "techpulse-dev-sources")
        self.region_name = region_name or os.getenv("AWS_REGION", "ap-south-1")
        self._table: Any | None = None

    @property
    def table(self) -> Any:
        if self._table is None:
            self._table = boto3.resource("dynamodb", region_name=self.region_name).Table(self.table_name)
        return self._table

    def all_enabled(self) -> list[dict[str, Any]]:
        """Bootstrap-scale scan; replace with a query/index if the registry grows significantly."""
        response = self.table.scan(FilterExpression=Attr("enabled").eq(True))
        items = list(response.get("Items", []))
        while response.get("LastEvaluatedKey"):
            response = self.table.scan(
                FilterExpression=Attr("enabled").eq(True),
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return items

    def upsert(self, item: dict[str, Any]) -> None:
        self.table.put_item(Item=item)

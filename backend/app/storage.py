"""DynamoDB persistence helpers with explicit conditional-write semantics."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import boto3
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
        """Atomic insert. Return False when a canonical update already exists."""
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(update_id)")
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

    def put_update_if_new(self, update: NormalizedUpdate) -> bool:
        """Persist a canonical update and prevent duplicate source notifications."""
        item = update.model_dump(mode="json")
        item["published_key"] = (
            update.published_at.astimezone(timezone.utc).isoformat()
            if update.published_at
            else update.observed_at.astimezone(timezone.utc).isoformat()
        ) + "#" + update.update_id
        item["first_seen_at"] = datetime.now(timezone.utc).isoformat()
        item["analysis_status"] = "pending"
        return self.put_if_absent(item)

    def query_by_technology(
        self,
        technology: str,
        *,
        limit: int = 20,
        exclusive_start_key: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "IndexName": os.getenv("TECHPULSE_UPDATE_INDEX", "technology-published-index"),
            "KeyConditionExpression": boto3.dynamodb.conditions.Key("technology").eq(technology),
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
        response = self.table.scan(FilterExpression="enabled = :yes", ExpressionAttributeValues={":yes": True})
        items = list(response.get("Items", []))
        while response.get("LastEvaluatedKey"):
            response = self.table.scan(
                FilterExpression="enabled = :yes",
                ExpressionAttributeValues={":yes": True},
                ExclusiveStartKey=response["LastEvaluatedKey"],
            )
            items.extend(response.get("Items", []))
        return items

    def upsert(self, item: dict[str, Any]) -> None:
        self.table.put_item(Item=item)

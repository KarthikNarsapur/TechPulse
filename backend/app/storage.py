"""Minimal DynamoDB storage adapter; boto3 clients are lazy for local tests."""
from __future__ import annotations

import os
from typing import Any

import boto3
from botocore.exceptions import ClientError


class UpdateStore:
    def __init__(self, table_name: str | None = None, *, region_name: str | None = None) -> None:
        self.table_name = table_name or os.getenv("TECHPULSE_UPDATES_TABLE", "techpulse-updates")
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self._table: Any | None = None

    @property
    def table(self) -> Any:
        if self._table is None:
            dynamodb = boto3.resource("dynamodb", region_name=self.region_name)
            self._table = dynamodb.Table(self.table_name)
        return self._table

    def get(self, update_id: str) -> dict[str, Any] | None:
        result = self.table.get_item(Key={"update_id": update_id}, ConsistentRead=True)
        return result.get("Item")

    def put_if_absent(self, item: dict[str, Any]) -> bool:
        """Atomic insert. Return False when an item with this canonical id exists."""
        try:
            self.table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(update_id)",
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
                return False
            raise

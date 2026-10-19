"""FastAPI application served through API Gateway and Mangum."""
import json
import os
from datetime import datetime, timezone
from typing import Any, Literal

import boto3
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, model_validator

from app.config import get_settings
from app.relevance import DEPARTMENT_RULES, classify_update
from app.source_registry import load_sources
from app.storage import PollStatusStore, SourceStore, SubscriptionStore, UpdateStore, UserStateStore

settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Serverless cloud and DevOps release intelligence API",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)

TECHNOLOGIES = [
    ("aws", "AWS", "cloud"),
    ("azure", "Azure", "cloud"),
    ("gcp", "Google Cloud", "cloud"),
    ("kubernetes", "Kubernetes", "containers"),
    ("terraform", "Terraform", "infrastructure-as-code"),
    ("gitlab", "GitLab", "ci-cd"),
]
SUPPORTED_TECHNOLOGY_IDS = {item[0] for item in TECHNOLOGIES}


class SubscriptionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: Literal["email", "slack", "teams"] = "email"
    secret_id: str | None = None


def _principal(request: Request) -> tuple[str, str | None]:
    """Read identity only from API Gateway's verified JWT authorizer claims."""
    event: dict[str, Any] = request.scope.get("aws.event", {})
    context = event.get("requestContext") or {}
    authorizer = context.get("authorizer") or {}
    jwt = authorizer.get("jwt") or {}
    claims = jwt.get("claims") or {}
    user_id = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip() or None
    email_verified = str(claims.get("email_verified") or "").lower() == "true"
    if not email_verified:
        email = None
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHENTICATED", "message": "A valid Cognito access token is required."},
        )
    return user_id, email


def _verified_email_from_access_token(request: Request) -> str | None:
    """Resolve a verified email through Cognito when it is absent from JWT claims."""
    event: dict[str, Any] = request.scope.get("aws.event", {})
    headers = event.get("headers") or {}
    authorization = str(headers.get("authorization") or headers.get("Authorization") or "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    response = boto3.client(
        "cognito-idp",
        region_name=os.getenv("TECHPULSE_AWS_REGION", os.getenv("AWS_REGION", "ap-south-1")),
    ).get_user(AccessToken=token.strip())
    attributes = {item.get("Name"): item.get("Value") for item in response.get("UserAttributes", [])}
    if str(attributes.get("email_verified", "")).lower() != "true":
        return None
    email = str(attributes.get("email") or "").strip()
    return email or None


def _public_subscription(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "technology_id": item["technology_id"],
        "channel": item.get("channel", "email"),
        "enabled": bool(item.get("enabled", True)),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "secret_configured": bool(item.get("secret_id")),
    }



class UserStateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    saved: bool | None = None
    read: bool | None = None

    @model_validator(mode="after")
    def require_a_state_change(self) -> "UserStateRequest":
        if self.saved is None and self.read is None:
            raise ValueError("At least one of saved or read must be provided.")
        return self


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "techpulse-api"}


@app.get("/api/v1/technologies")
def technologies() -> dict[str, list[dict[str, str]]]:
    values = TECHNOLOGIES
    return {"items": [{"id": key, "name": name, "category": category} for key, name, category in values]}


@app.get("/api/v1/updates")
def list_updates(
    technology: str | None = None,
    category: str | None = None,
    department: str | None = None,
    days: int = Query(default=7, ge=1, le=90),
    limit: int = Query(default=100, ge=1, le=100),
) -> dict[str, Any]:
    store = UpdateStore()
    if technology:
        result = store.query_by_technology(technology, limit=limit)
    else:
        result = store.query_all(limit=limit)
    items = result["items"]
    last_key = result.get("last_evaluated_key")
    cutoff = datetime.now(timezone.utc).timestamp() - days * 86400
    recent_items = []
    for item in items:
        timestamp = item.get("published_at") or item.get("observed_at")
        if not timestamp:
            continue
        try:
            parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            if parsed.timestamp() < cutoff:
                continue
        except (TypeError, ValueError, OverflowError):
            continue
        recent_items.append(item)
    items = recent_items
    if category:
        items = [item for item in items if item.get("category") == category]
    items = [classify_update(dict(item)) for item in items]
    if department:
        if department not in DEPARTMENT_RULES:
            raise HTTPException(status_code=422, detail={"message": "Unknown department workspace."})
        items = [item for item in items if department in item["department_relevance"]]
        items.sort(key=lambda item: (item["department_relevance_scores"].get(department, 0), item.get("published_at") or item.get("observed_at") or ""), reverse=True)
    return {
        "items": items,
        "next_cursor": last_key,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/refresh")
def refresh_updates(request: Request) -> dict[str, Any]:
    """Queue a source poll for the official sources; callers must be authenticated."""
    _principal(request)
    queue_url = os.getenv("TECHPULSE_INGESTION_QUEUE_URL")
    if not queue_url:
        raise HTTPException(status_code=503, detail={"message": "Ingestion queue is not configured."})

    # The checked-in registry controls enabled official sources. Persisted entries
    # may add custom sources, but stale table rows must not disable registry updates.
    sources_by_id = {source.source_id: source.model_dump(mode="json") for source in load_sources()}
    table_name = os.getenv("TECHPULSE_SOURCES_TABLE")
    if table_name:
        try:
            for source in SourceStore(table_name).all_enabled():
                sources_by_id.setdefault(str(source["source_id"]), source)
        except Exception:
            pass
    enabled = [source for source in sources_by_id.values() if source.get("enabled", True)]
    if not enabled:
        raise HTTPException(status_code=503, detail={"message": "No enabled sources are configured."})

    queue = boto3.client("sqs", region_name=os.getenv("AWS_REGION", "ap-south-1"))
    for source in enabled:
        queue.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps({"source_id": source["source_id"]}),
        )
    return {"queued_sources": len(enabled), "source_ids": [source["source_id"] for source in enabled]}


@app.get("/api/v1/updates/{update_id}")
def get_update(update_id: str) -> dict[str, Any]:
    item = UpdateStore().get(update_id)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Update not found."})
    return item




@app.get("/api/v1/user-state")
def list_user_state(request: Request) -> dict[str, list[dict[str, Any]]]:
    user_id, _ = _principal(request)
    items = UserStateStore().list_for_user(user_id)
    return {"items": [
        {
            "update_id": item["update_id"],
            "saved": bool(item.get("saved", False)),
            "read": bool(item.get("read", False)),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
        }
        for item in items
    ]}


@app.put("/api/v1/user-state/{update_id}")
def put_user_state(update_id: str, body: UserStateRequest, request: Request) -> dict[str, Any]:
    user_id, _ = _principal(request)
    if not UpdateStore().get(update_id):
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Update not found."})

    store = UserStateStore()
    existing = store.get(user_id, update_id) or {}
    now = datetime.now(timezone.utc).isoformat()
    item = {
        "user_id": user_id,
        "update_id": update_id,
        "saved": existing.get("saved", False) if body.saved is None else body.saved,
        "read": existing.get("read", False) if body.read is None else body.read,
        "created_at": existing.get("created_at", now),
        "updated_at": now,
    }
    store.put(item)
    return {"item": {
        "update_id": update_id,
        "saved": item["saved"],
        "read": item["read"],
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }}


@app.get("/api/v1/source-status")
def source_status(request: Request) -> dict[str, Any]:
    """Return safe polling checkpoints to signed-in users; never expose source credentials."""
    _principal(request)
    fields = (
        "source_id",
        "poll_status",
        "poll_attempts",
        "last_poll_started_at",
        "last_poll_completed_at",
        "last_poll_success_at",
        "last_poll_fetched",
        "last_poll_new",
        "last_poll_changed",
        "last_poll_error_type",
    )
    items = PollStatusStore().list_status()
    return {"items": [{key: item[key] for key in fields if key in item} for item in items]}


@app.get("/api/v1/subscriptions")
def list_subscriptions(request: Request) -> dict[str, list[dict[str, Any]]]:
    user_id, _ = _principal(request)
    items = SubscriptionStore().list_for_user(user_id)
    return {"items": [_public_subscription(item) for item in items]}


@app.put("/api/v1/subscriptions/{technology_id}")
def put_subscription(
    technology_id: str,
    body: SubscriptionRequest,
    request: Request,
) -> dict[str, Any]:
    user_id, email = _principal(request)
    if technology_id not in SUPPORTED_TECHNOLOGY_IDS:
        raise HTTPException(
            status_code=404,
            detail={"code": "UNKNOWN_TECHNOLOGY", "message": "Technology is not in the supported registry."},
        )

    environment = os.getenv("TECHPULSE_ENVIRONMENT", "dev")
    item: dict[str, Any] = {
        "user_id": user_id,
        "technology_id": technology_id,
        "channel": body.channel,
        "enabled": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    existing = SubscriptionStore().get(user_id, technology_id)
    item["created_at"] = (existing or {}).get("created_at", item["updated_at"])

    if body.channel == "email":
        if not email:
            email = _verified_email_from_access_token(request)
        if not email:
            raise HTTPException(
                status_code=422,
                detail={"code": "EMAIL_REQUIRED", "message": "The signed-in account has no verified email claim."},
            )
        item["email"] = email
    else:
        expected_prefix = f"techpulse-{environment}-notifications-{body.channel}"
        secret_id = (body.secret_id or "").strip()
        if not secret_id.startswith(expected_prefix):
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_SECRET_REFERENCE",
                    "message": f"Use a pre-created secret ID beginning with {expected_prefix}.",
                },
            )
        item["secret_id"] = secret_id

    SubscriptionStore().put(item)
    return {"item": _public_subscription(item)}


@app.delete("/api/v1/subscriptions/{technology_id}")
def delete_subscription(technology_id: str, request: Request) -> dict[str, bool]:
    user_id, _ = _principal(request)
    if technology_id not in SUPPORTED_TECHNOLOGY_IDS:
        raise HTTPException(
            status_code=404,
            detail={"code": "UNKNOWN_TECHNOLOGY", "message": "Technology is not in the supported registry."},
        )
    SubscriptionStore().delete(user_id, technology_id)
    return {"deleted": True}

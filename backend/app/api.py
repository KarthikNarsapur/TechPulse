"""FastAPI application served through API Gateway and Mangum."""
import os
from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict

from app.config import get_settings
from app.storage import SubscriptionStore, UpdateStore

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
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHENTICATED", "message": "A valid Cognito access token is required."},
        )
    return user_id, email


def _public_subscription(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "technology_id": item["technology_id"],
        "channel": item.get("channel", "email"),
        "enabled": bool(item.get("enabled", True)),
        "created_at": item.get("created_at"),
        "updated_at": item.get("updated_at"),
        "secret_configured": bool(item.get("secret_id")),
    }


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
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    store = UpdateStore()
    if technology:
        result = store.query_by_technology(technology, limit=limit)
    else:
        result = store.query_all(limit=limit)
    items = result["items"]
    last_key = result.get("last_evaluated_key")
    if category:
        items = [item for item in items if item.get("category") == category]
    return {
        "items": items,
        "next_cursor": last_key,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/v1/updates/{update_id}")
def get_update(update_id: str) -> dict[str, Any]:
    item = UpdateStore().get(update_id)
    if not item:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Update not found."})
    return item


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

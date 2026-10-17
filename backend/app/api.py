"""FastAPI application served through API Gateway and Mangum."""
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.storage import UpdateStore

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "techpulse-api"}


@app.get("/api/v1/technologies")
def technologies() -> dict[str, list[dict[str, str]]]:
    values = [
        ("aws", "AWS", "cloud"),
        ("azure", "Azure", "cloud"),
        ("gcp", "Google Cloud", "cloud"),
        ("kubernetes", "Kubernetes", "containers"),
        ("terraform", "Terraform", "infrastructure-as-code"),
        ("gitlab", "GitLab", "ci-cd"),
    ]
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

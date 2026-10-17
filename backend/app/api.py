"""FastAPI application used by API Gateway through Mangum."""
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

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
    """Feed API contract. Storage/index query is wired in the persistence increment."""
    return {
        "items": [],
        "next_cursor": None,
        "filters": {"technology": technology, "category": category, "limit": limit},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "storage_not_configured",
    }


@app.get("/api/v1/updates/{update_id}")
def get_update(update_id: str) -> dict[str, Any]:
    # The API must not pretend that an unconfigured datastore returned a 404.
    raise HTTPException(
        status_code=503,
        detail={"code": "STORAGE_NOT_CONFIGURED", "message": "Update storage is not configured yet."},
    )

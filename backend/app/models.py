"""Canonical data contracts shared by API and worker code."""
from datetime import datetime, timezone
from enum import StrEnum
from hashlib import sha256
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class SourceType(StrEnum):
    RSS = "rss"
    ATOM = "atom"
    GITHUB_RELEASES = "github_releases"
    JSON_API = "json_api"


class UpdateCategory(StrEnum):
    NEW_FEATURE = "new_feature"
    RELEASE = "release"
    BREAKING_CHANGE = "breaking_change"
    DEPRECATION = "deprecation"
    SECURITY_ADVISORY = "security_advisory"
    BUG_FIX = "bug_fix"
    PRICING_CHANGE = "pricing_change"
    DOCUMENTATION_CHANGE = "documentation_change"
    OTHER = "other"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=2, max_length=128)
    vendor: str = Field(min_length=1, max_length=80)
    technology: str = Field(min_length=1, max_length=80)
    source_type: SourceType
    url: HttpUrl
    repository: str | None = None
    poll_interval_minutes: int = Field(default=60, ge=5, le=10080)
    include_prereleases: bool = False
    enabled: bool = True
    trust_level: str = "official"


class NormalizedUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    update_id: str
    source_id: str
    vendor: str
    technology: str
    title: str = Field(min_length=1, max_length=500)
    canonical_url: HttpUrl
    published_at: datetime | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    content_text: str = ""
    content_hash: str
    external_id: str | None = None
    category: UpdateCategory = UpdateCategory.OTHER
    priority: Priority = Priority.INFORMATIONAL

    @staticmethod
    def normalize_url(url: str) -> str:
        """Drop common tracking parameters and fragments before fingerprinting."""
        parts = urlsplit(url)
        kept = []
        for pair in parts.query.split("&") if parts.query else []:
            key = pair.split("=", 1)[0].lower()
            if key and not (key.startswith("utm_") or key in {"source", "ref", "fbclid"}):
                kept.append(pair)
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "&".join(kept), ""))

    @classmethod
    def fingerprint(cls, source_id: str, external_id: str | None, url: str, title: str, text: str) -> str:
        identity = external_id or cls.normalize_url(url)
        canonical = "\n".join([source_id, identity, " ".join(title.split()).casefold(), " ".join(text.split())])
        return sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def make_id(cls, url: str) -> str:
        return sha256(cls.normalize_url(url).encode("utf-8")).hexdigest()


class AnalysisResult(BaseModel):
    """Schema expected from the single structured AI call.

    Evidence fields must cite source text or source URLs; unknown values are
    preferred over unsupported version or availability claims.
    """

    summary: str = Field(min_length=1, max_length=3000)
    category: UpdateCategory
    affected_technologies: list[str] = Field(default_factory=list)
    affected_versions: list[str] = Field(default_factory=list)
    availability_stage: str = "unknown"
    breaking_change: bool = False
    deprecation: bool = False
    security_relevance: str = "unknown"
    recommended_actions: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    requires_human_review: bool = False


def deterministic_priority(
    *,
    category: UpdateCategory,
    evidence_confidence: float,
    confirmed_exposure: bool = False,
    urgent_deadline: bool = False,
) -> Priority:
    """Simple, auditable baseline; never lets an LLM directly set final priority."""
    if category == UpdateCategory.SECURITY_ADVISORY and confirmed_exposure and evidence_confidence >= 0.8:
        return Priority.CRITICAL
    if urgent_deadline or category in {UpdateCategory.BREAKING_CHANGE, UpdateCategory.DEPRECATION}:
        return Priority.HIGH
    if category in {UpdateCategory.SECURITY_ADVISORY, UpdateCategory.NEW_FEATURE, UpdateCategory.RELEASE}:
        return Priority.MEDIUM
    if category in {UpdateCategory.BUG_FIX, UpdateCategory.PRICING_CHANGE}:
        return Priority.LOW
    return Priority.INFORMATIONAL

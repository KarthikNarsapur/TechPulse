"""Deterministic, explainable department relevance for TechPulse updates."""

from __future__ import annotations

import re
from typing import Any

# IDs mirror the department workspace selector. These rules rank updates; they
# are not authorization boundaries and should not be treated as an HR directory.
DEPARTMENT_RULES: dict[str, tuple[tuple[str, ...], ...]] = {
    "tc-migration-finops": (
        (
            "migration",
            "migrate",
            "migrating",
            "transform",
            "modernization",
            "modernisation",
            "cloud adoption",
            "disaster recovery",
            "replication",
            "data transfer",
            "dms",
            "database migration",
            "vmware",
            "azure to aws",
            "aws to azure",
            "cross-region",
            "cross account",
        ),
        (
            "finops",
            "cost optimization",
            "cost optimisation",
            "cost management",
            "pricing",
            "price reduction",
            "savings plan",
            "reserved instance",
            "compute optimizer",
            "billing",
            "budgets",
            "cost explorer",
            "rightsizing",
            "right-sizing",
            "spend",
            "unit economics",
        ),
        (
            "terraform",
            "infrastructure as code",
            "iac",
            "kubernetes",
            "eks",
            "aks",
            "gke",
            "container",
            "networking",
            "vpc",
            "vnet",
            "vpn",
            "load balancer",
            "cloudformation",
            "bicep",
            "landing zone",
        ),
    ),
    "tc-data-aiot": (
        (
            "data warehouse",
            "data lake",
            "analytics",
            "machine learning",
            "generative ai",
            "bedrock",
            "sagemaker",
            "vertex ai",
            "azure ai",
            "iot",
            "database",
            "postgres",
            "mysql",
            "dynamodb",
            "redshift",
            "bigquery",
            "synapse",
            "fabric",
        ),
    ),
    "tc-development": (
        (
            "sdk",
            "api",
            "developer",
            "runtime",
            "programming language",
            "java",
            "python",
            "node.js",
            "dotnet",
            ".net",
            "code conversion",
            "ide",
            "gitlab",
            "ci/cd",
            "pipeline",
            "build",
        ),
    ),
    "tc-devops-kubernetes": (
        (
            "kubernetes",
            "kubectl",
            "helm",
            "container",
            "eks",
            "aks",
            "gke",
            "terraform",
            "ci/cd",
            "pipeline",
            "gitlab",
            "github actions",
            "deployment",
            "observability",
            "prometheus",
            "grafana",
            "service mesh",
        ),
    ),
    "tc-general": (
        (
            "infrastructure",
            "architecture",
            "resilience",
            "reliability",
            "well-architected",
            "cloud foundation",
            "landing zone",
        ),
    ),
    "tc-infra-security": (
        (
            "security",
            "vulnerability",
            "cve-",
            "iam",
            "identity",
            "encryption",
            "kms",
            "firewall",
            "compliance",
            "audit",
            "zero trust",
            "threat",
            "guardduty",
            "defender",
            "policy",
            "network security",
        ),
    ),
    "tc-it-support": (
        (
            "support",
            "service health",
            "incident",
            "troubleshoot",
            "maintenance",
            "end of support",
            "end-of-life",
            "eol",
            "status dashboard",
        ),
    ),
    "tc-ld-content": (
        (
            "certification",
            "training",
            "learning path",
            "course",
            "exam",
            "documentation",
            "tutorial",
            "workshop",
            "skill builder",
        ),
    ),
    "tc-managed-services": (
        (
            "managed service",
            "operations",
            "monitoring",
            "backup",
            "patch",
            "maintenance window",
            "service level",
            "sla",
            "incident management",
            "observability",
        ),
    ),
    "tc-presales": (
        (
            "solution architecture",
            "reference architecture",
            "partner solution",
            "partner program",
            "marketplace listing",
            "proof of concept",
            "customer solution",
            "sales engineering",
        ),
    ),
    "ts-ms-programs": (
        (
            "microsoft",
            "azure",
            "m365",
            "microsoft 365",
            "copilot",
            "windows server",
            "entra",
            "power platform",
        ),
    ),
    "ts-corporate-accounts": (
        (
            "corporate account",
            "enterprise agreement",
            "enterprise customer",
            "organization-wide",
            "organisation-wide",
            "commercial account",
            "account team",
            "license management",
        ),
    ),
    "ts-inside-sales": (
        (
            "inside sales",
            "sales enablement",
            "sales playbook",
            "lead qualification",
            "sales pipeline",
            "commercial pricing",
            "license sales",
            "sales training",
        ),
    ),
    "ts-demand-generation": (
        (
            "demand generation",
            "marketing campaign",
            "lead generation",
            "campaign asset",
            "marketing qualified lead",
            "customer webinar",
            "event registration",
            "product marketing",
        ),
    ),
    "general": (
        ("release", "security", "availability", "breaking change", "deprecation", "new feature"),
    ),
}


def classify_update(item: dict[str, Any]) -> dict[str, Any]:
    """Attach department relevance, preserving successful model classifications."""
    # Any model provider (groq, anthropic) wins over keyword rules once it has classified.
    if item.get("relevance_provider") not in (None, "", "deterministic") and isinstance(
        item.get("department_relevance"), list
    ):
        return item
    title = str(item.get("title") or "")
    body = str(item.get("content_text") or item.get("summary") or "")
    technology = str(item.get("technology") or "").lower()
    category = str(item.get("category") or "").lower()
    source_id = str(item.get("source_id") or "").lower()
    text = re.sub(r"\s+", " ", f"{title} {body} {technology} {category} {source_id}").lower()

    matched: dict[str, list[str]] = {}
    scores: dict[str, int] = {}
    for department_id, rule_groups in DEPARTMENT_RULES.items():
        topics: list[str] = []
        score = 0
        for group_index, keywords in enumerate(rule_groups):
            hits = [keyword for keyword in keywords if keyword in text]
            if hits:
                score += (5 if group_index == 0 else 4 if group_index == 1 else 2) + min(
                    len(hits) - 1, 2
                )
                topics.extend(hits[:3])
        if department_id == "tc-migration-finops" and technology in {"terraform", "kubernetes"}:
            score += 2
            topics.append(technology)
        if score >= (
            2
            if department_id == "tc-migration-finops" and technology in {"terraform", "kubernetes"}
            else 4
        ):
            matched[department_id] = list(dict.fromkeys(topics))[:6]
            scores[department_id] = score

    if not matched:
        matched["tc-general"] = ["shared cloud update"]
        scores["tc-general"] = 1
        matched["general"] = ["shared update"]
        scores["general"] = 1

    item["department_relevance"] = sorted(matched)
    item["relevance_topics"] = matched
    item["department_relevance_scores"] = scores
    item["primary_department"] = max(scores, key=scores.get) if scores else "general"
    return item


PRIORITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "informational": 0}
# Unassessed impact sorts above a confirmed low impact: unknown may still matter.
IMPACT_RANK = {"high": 3, "medium": 2, None: 1, "low": 0}


def workspace_rank(item: dict[str, Any], department: str) -> tuple[Any, ...]:
    """Sort key (use reverse=True) for one workspace's feed.

    Deterministic critical priority always leads; the model's advisory business impact
    then ranks above the deterministic priority, relevance score, and recency.
    """
    priority = str(item.get("priority") or "informational")
    impact = (item.get("department_impact") or {}).get(department) or {}
    return (
        priority == "critical",
        IMPACT_RANK.get(impact.get("level"), 1),
        PRIORITY_RANK.get(priority, 0),
        (item.get("department_relevance_scores") or {}).get(department, 0),
        item.get("published_at") or item.get("observed_at") or "",
    )

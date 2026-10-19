"""Deterministic, explainable department relevance for TechPulse updates."""
from __future__ import annotations

import re
from typing import Any

# IDs mirror the department workspace selector. These rules rank updates; they
# are not authorization boundaries and should not be treated as an HR directory.
DEPARTMENT_RULES: dict[str, tuple[tuple[str, ...], ...]] = {
    "tc-migration-finops": (
        ("migration", "migrate", "migrating", "transform", "modernization", "modernisation", "cloud adoption", "disaster recovery", "replication", "data transfer", "dms", "database migration", "vmware", "azure to aws", "aws to azure", "cross-region", "cross account"),
        ("finops", "cost optimization", "cost optimisation", "cost management", "pricing", "price reduction", "savings plan", "reserved instance", "compute optimizer", "billing", "budgets", "cost explorer", "rightsizing", "right-sizing", "spend", "unit economics"),
        ("terraform", "infrastructure as code", "iac", "kubernetes", "eks", "aks", "gke", "container", "networking", "vpc", "vnet", "vpn", "load balancer", "cloudformation", "bicep", "landing zone"),
    ),
    "tc-data-aiot": (("data warehouse", "data lake", "analytics", "machine learning", "generative ai", "bedrock", "sagemaker", "vertex ai", "azure ai", "iot", "database", "postgres", "mysql", "dynamodb", "redshift", "bigquery", "synapse", "fabric"),),
    "tc-development": (("sdk", "api", "developer", "runtime", "programming language", "java", "python", "node.js", "dotnet", ".net", "code conversion", "ide", "gitlab", "ci/cd", "pipeline", "build"),),
    "tc-devops-kubernetes": (("kubernetes", "kubectl", "helm", "container", "eks", "aks", "gke", "terraform", "ci/cd", "pipeline", "gitlab", "github actions", "deployment", "observability", "prometheus", "grafana", "service mesh"),),
    "tc-general": (("cloud", "infrastructure", "architecture", "availability", "region", "resilience", "reliability", "well-architected"),),
    "tc-infra-security": (("security", "vulnerability", "cve-", "iam", "identity", "encryption", "kms", "firewall", "compliance", "audit", "zero trust", "threat", "guardduty", "defender", "policy", "network security"),),
    "tc-it-support": (("support", "service health", "incident", "troubleshoot", "maintenance", "end of support", "end-of-life", "eol", "status dashboard"),),
    "tc-ld-content": (("certification", "training", "learning path", "course", "exam", "documentation", "tutorial", "workshop", "skill builder"),),
    "tc-managed-services": (("managed service", "operations", "monitoring", "backup", "patch", "maintenance window", "service level", "sla", "incident management", "observability"),),
    "tc-presales": (("preview", "generally available", "launch", "new service", "solution", "reference architecture", "partner", "marketplace", "proof of concept"),),
    "ts-ms-programs": (("microsoft", "azure", "m365", "microsoft 365", "copilot", "windows server", "entra", "power platform"),),
    "ts-corporate-accounts": (("enterprise", "organization", "organisation", "account", "pricing", "subscription", "license", "licence", "business"),),
    "ts-inside-sales": (("pricing", "subscription", "license", "licence", "plan", "product launch", "generally available"),),
    "ts-demand-generation": (("launch", "generally available", "new feature", "new service", "preview", "announcement"),),
    "hr-finance": (("billing", "cost", "pricing", "invoice", "budget", "workforce", "hr", "finance"),),
    "general": (("release", "security", "availability", "breaking change", "deprecation", "new feature"),),
}


def classify_update(item: dict[str, Any]) -> dict[str, Any]:
    """Attach department IDs, matching topics, and transparent relevance scores."""
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
                score += (5 if group_index == 0 else 4 if group_index == 1 else 2) + min(len(hits) - 1, 2)
                topics.extend(hits[:3])
        if department_id == "tc-migration-finops" and technology in {"terraform", "kubernetes"}:
            score += 2
            topics.append(technology)
        if score:
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

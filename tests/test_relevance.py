from app.relevance import classify_update


def test_migration_finops_prioritizes_migration_and_cost_updates() -> None:
    update = classify_update({
        "title": "AWS Transform expands migration support and lowers migration costs",
        "technology": "aws",
        "source_id": "aws.whats_new",
        "category": "new_feature",
        "content_text": "Cloud migration, cost optimization, and VMware modernization.",
    })
    assert "tc-migration-finops" in update["department_relevance"]
    assert update["department_relevance_scores"]["tc-migration-finops"] >= 9
    assert "migration" in update["relevance_topics"]["tc-migration-finops"]


def test_terraform_and_kubernetes_updates_are_visible_to_migration_finops() -> None:
    for technology in ("terraform", "kubernetes"):
        update = classify_update({
            "title": f"New {technology} release",
            "technology": technology,
            "source_id": f"{technology}.releases",
            "content_text": "Bug fixes and general improvements.",
        })
        assert "tc-migration-finops" in update["department_relevance"]
        assert update["department_relevance_scores"]["tc-migration-finops"] >= 2


def test_infrastructure_security_and_devops_are_classified_separately() -> None:
    security = classify_update({
        "title": "IAM security policy update",
        "technology": "aws",
        "source_id": "aws.whats_new",
        "content_text": "Identity and encryption improvements.",
    })
    devops = classify_update({
        "title": "Kubernetes release adds deployment improvements",
        "technology": "kubernetes",
        "source_id": "kubernetes.releases",
        "content_text": "Container and deployment updates.",
    })
    assert "tc-infra-security" in security["department_relevance"]
    assert "tc-devops-kubernetes" in devops["department_relevance"]


def test_unmatched_update_still_appears_in_shared_workspaces() -> None:
    update = classify_update({
        "title": "Minor product note",
        "technology": "aws",
        "source_id": "aws.whats_new",
        "content_text": "",
    })
    assert "tc-general" in update["department_relevance"]
    assert "general" in update["department_relevance"]


def test_hr_workspace_is_not_a_relevance_destination() -> None:
    update = classify_update({
        "title": "Cloud service pricing and billing changes",
        "technology": "aws",
        "source_id": "aws.whats_new",
        "content_text": "Updated cost and budget reporting.",
    })
    assert "hr-finance" not in update["department_relevance"]


def test_generic_launch_does_not_route_to_sales_workspaces() -> None:
    update = classify_update({
        "title": "A new feature is now generally available",
        "technology": "aws",
        "source_id": "aws.whats_new",
        "content_text": "The service now supports a new release.",
    })
    assert "ts-demand-generation" not in update["department_relevance"]
    assert "ts-inside-sales" not in update["department_relevance"]
    assert "ts-corporate-accounts" not in update["department_relevance"]

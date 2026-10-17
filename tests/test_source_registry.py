from pathlib import Path

import pytest

from app.source_registry import load_sources


def test_registry_has_initial_source_records() -> None:
    path = Path(__file__).parents[1] / "source-registry" / "sources.yaml"
    sources = load_sources(path, enabled_only=False)
    ids = {source.source_id for source in sources}
    assert {
        "aws.whats_new",
        "azure.updates",
        "gcp.release_notes",
        "kubernetes.releases",
        "terraform.cli_releases",
        "gitlab.release_notes",
    }.issubset(ids)


def test_duplicate_source_ids_are_rejected(tmp_path: Path) -> None:
    registry = tmp_path / "sources.yaml"
    registry.write_text(
        """sources:
  - source_id: duplicate
    vendor: test
    technology: test
    source_type: rss
    url: https://example.com/a
  - source_id: duplicate
    vendor: test
    technology: test
    source_type: rss
    url: https://example.com/b
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unique"):
        load_sources(registry)

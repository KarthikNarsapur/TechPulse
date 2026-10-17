"""Load and validate the source registry."""
from pathlib import Path
from typing import Any

import yaml

from app.models import SourceConfig


DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parents[2] / "source-registry" / "sources.yaml"


def load_sources(path: Path = DEFAULT_REGISTRY_PATH, *, enabled_only: bool = True) -> list[SourceConfig]:
    """Load registry entries; URL reachability is checked by source validation jobs."""
    raw: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("sources", [])
    sources = [SourceConfig.model_validate(entry) for entry in entries]
    ids = [source.source_id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("source_id values must be unique")
    return [source for source in sources if source.enabled or not enabled_only]

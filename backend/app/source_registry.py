"""Load and validate the source registry from disk or the Lambda package."""

import os
from pathlib import Path
from typing import Any

import yaml

from app.models import SourceConfig


def _candidate_paths() -> list[Path]:
    configured = os.getenv("TECHPULSE_SOURCE_REGISTRY_PATH")
    candidates = [Path(configured)] if configured else []
    module_path = Path(__file__).resolve()
    # Local source tree: repo/source-registry. Lambda archive: /var/task/source-registry.
    candidates.extend(
        [
            module_path.parents[2] / "source-registry" / "sources.yaml",
            module_path.parents[1] / "source-registry" / "sources.yaml",
            Path.cwd() / "source-registry" / "sources.yaml",
        ]
    )
    return list(dict.fromkeys(candidates))


def load_sources(path: Path | None = None, *, enabled_only: bool = True) -> list[SourceConfig]:
    """Load registry entries; source reachability is verified separately."""
    chosen = path or next(
        (candidate for candidate in _candidate_paths() if candidate.is_file()), None
    )
    if chosen is None:
        raise FileNotFoundError("source-registry/sources.yaml was not packaged or configured")
    raw: dict[str, Any] = yaml.safe_load(chosen.read_text(encoding="utf-8")) or {}
    entries = raw.get("sources", [])
    sources = [SourceConfig.model_validate(entry) for entry in entries]
    ids = [source.source_id for source in sources]
    if len(ids) != len(set(ids)):
        raise ValueError("source_id values must be unique")
    return [source for source in sources if source.enabled or not enabled_only]

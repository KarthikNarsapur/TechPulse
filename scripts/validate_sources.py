#!/usr/bin/env python3
"""Validate live configured sources before enabling them.

Examples:
  python scripts/validate_sources.py
  python scripts/validate_sources.py --all --json
  python scripts/validate_sources.py --strict

Network validation is intentionally opt-in in CI because vendor feeds can
rate-limit or have temporary outages.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.adapters.registry import fetch_source  # noqa: E402
from app.models import SourceConfig  # noqa: E402
from app.source_registry import load_sources  # noqa: E402


@dataclass
class ValidationResult:
    source_id: str
    source_type: str
    url: str
    enabled: bool
    status: str
    entries: int = 0
    sample_title: str | None = None
    error: str | None = None


def validate(source: SourceConfig) -> ValidationResult:
    try:
        entries = fetch_source(source)
        if not entries:
            return ValidationResult(
                source_id=source.source_id,
                source_type=source.source_type.value,
                url=str(source.url),
                enabled=source.enabled,
                status="empty",
                error="Fetch/parse succeeded but no usable entries were returned.",
            )
        return ValidationResult(
            source_id=source.source_id,
            source_type=source.source_type.value,
            url=str(source.url),
            enabled=source.enabled,
            status="passed",
            entries=len(entries),
            sample_title=entries[0].title,
        )
    except Exception as exc:  # noqa: BLE001 - report each source without aborting the run
        return ValidationResult(
            source_id=source.source_id,
            source_type=source.source_type.value,
            url=str(source.url),
            enabled=source.enabled,
            status="failed",
            error=f"{type(exc).__name__}: {str(exc)[:300]}",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="Validate disabled sources too.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero unless every selected source passes.")
    parser.add_argument("--json", action="store_true", help="Print a JSON report.")
    args = parser.parse_args()

    registry = ROOT / "source-registry" / "sources.yaml"
    sources = load_sources(registry, enabled_only=not args.all)
    results = [validate(source) for source in sources]

    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for result in results:
            marker = "PASS" if result.status == "passed" else "FAIL"
            print(f"[{marker}] {result.source_id}: {result.status}; entries={result.entries}; url={result.url}")
            if result.sample_title:
                print(f"       sample: {result.sample_title}")
            if result.error:
                print(f"       detail: {result.error}")

    return 1 if args.strict and any(item.status != "passed" for item in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())

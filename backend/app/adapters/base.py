"""Source adapter contracts."""
from typing import Protocol

from app.models import NormalizedUpdate, SourceConfig


class SourceAdapter(Protocol):
    def fetch(self, source: SourceConfig) -> list[NormalizedUpdate]:
        """Fetch and normalize recent announcements from a configured source."""

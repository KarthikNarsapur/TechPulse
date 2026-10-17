from datetime import datetime, timezone

from app.models import NormalizedUpdate, Priority, UpdateCategory, deterministic_priority


def test_url_normalization_removes_tracking_parameters() -> None:
    url = "https://EXAMPLE.com/releases/v1/?utm_campaign=test&ref=homepage#notes"
    assert NormalizedUpdate.normalize_url(url) == "https://example.com/releases/v1"


def test_same_url_has_same_update_id() -> None:
    left = NormalizedUpdate.make_id("https://example.com/a?utm_source=email")
    right = NormalizedUpdate.make_id("https://example.com/a")
    assert left == right


def test_fingerprint_is_stable_for_whitespace_variations() -> None:
    a = NormalizedUpdate.fingerprint("x", "123", "https://example.com", " New   Feature ", "line one\n line two")
    b = NormalizedUpdate.fingerprint("x", "123", "https://example.com", "new feature", "line one line two")
    assert a == b


def test_deterministic_priority_for_confirmed_security_exposure() -> None:
    assert deterministic_priority(
        category=UpdateCategory.SECURITY_ADVISORY,
        evidence_confidence=0.95,
        confirmed_exposure=True,
    ) == Priority.CRITICAL


def test_unknown_security_exposure_does_not_become_critical() -> None:
    assert deterministic_priority(
        category=UpdateCategory.SECURITY_ADVISORY,
        evidence_confidence=0.95,
        confirmed_exposure=False,
    ) == Priority.MEDIUM


def test_normalized_update_model() -> None:
    update = NormalizedUpdate(
        update_id="abc",
        source_id="test",
        vendor="example",
        technology="terraform",
        title="v1.2 released",
        canonical_url="https://example.com/release",
        published_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        content_hash="hash",
    )
    assert update.technology == "terraform"

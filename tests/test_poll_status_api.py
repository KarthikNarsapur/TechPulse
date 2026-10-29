from unittest.mock import MagicMock

from starlette.requests import Request

from app.api import source_status


def _authenticated_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/source-status",
            "headers": [],
            "query_string": b"",
            "server": ("test", 80),
            "client": ("test", 1),
            "scheme": "https",
            "aws.event": {
                "requestContext": {
                    "authorizer": {
                        "jwt": {
                            "claims": {
                                "sub": "user-123",
                                "email": "user@example.com",
                                "email_verified": "true",
                            }
                        }
                    }
                }
            },
        }
    )


def test_source_status_returns_only_safe_checkpoint_fields(monkeypatch) -> None:
    store = MagicMock()
    store.list_status.return_value = [
        {
            "source_id": "aws-release",
            "poll_status": "failed",
            "poll_attempts": 4,
            "last_poll_error_type": "TimeoutError",
            "secret": "must-not-be-returned",
        }
    ]
    monkeypatch.setattr("app.api.PollStatusStore", lambda: store)

    response = source_status(_authenticated_request())

    assert response["items"] == [
        {
            "source_id": "aws-release",
            "poll_status": "failed",
            "poll_attempts": 4,
            "last_poll_error_type": "TimeoutError",
        }
    ]

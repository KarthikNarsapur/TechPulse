from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api import UserStateRequest, list_user_state, put_user_state


def _request(user_id: str = "user-123") -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/user-state",
            "headers": [],
            "query_string": b"",
            "server": ("test", 80),
            "client": ("test", 1),
            "scheme": "https",
            "aws.event": {"requestContext": {"authorizer": {"jwt": {"claims": {"sub": user_id}}}}},
        }
    )


def test_user_state_list_is_scoped_to_verified_principal(monkeypatch) -> None:
    store = MagicMock()
    store.list_for_user.return_value = [
        {"update_id": "update-1", "saved": True, "read": False, "user_id": "user-123"}
    ]
    monkeypatch.setattr("app.api.UserStateStore", lambda: store)

    result = list_user_state(_request())

    store.list_for_user.assert_called_once_with("user-123")
    assert result["items"] == [
        {
            "update_id": "update-1",
            "saved": True,
            "read": False,
            "created_at": None,
            "updated_at": None,
        }
    ]


def test_user_state_update_preserves_unspecified_flag(monkeypatch) -> None:
    store = MagicMock()
    store.get.return_value = {
        "user_id": "user-123",
        "update_id": "update-1",
        "saved": True,
        "read": False,
        "created_at": "2026-01-01T00:00:00+00:00",
    }
    monkeypatch.setattr("app.api.UserStateStore", lambda: store)
    monkeypatch.setattr(
        "app.api.UpdateStore", lambda: MagicMock(get=lambda _update_id: {"update_id": "update-1"})
    )

    result = put_user_state("update-1", UserStateRequest(read=True), _request())

    persisted = store.put.call_args.args[0]
    assert persisted["user_id"] == "user-123"
    assert persisted["saved"] is True
    assert persisted["read"] is True
    assert persisted["created_at"] == "2026-01-01T00:00:00+00:00"
    assert result["item"]["read"] is True


def test_user_state_rejects_empty_patch() -> None:
    with pytest.raises(ValueError, match="At least one"):
        UserStateRequest()


def test_user_state_rejects_unknown_update(monkeypatch) -> None:
    monkeypatch.setattr("app.api.UpdateStore", lambda: MagicMock(get=lambda _update_id: None))
    store = MagicMock()
    monkeypatch.setattr("app.api.UserStateStore", lambda: store)

    with pytest.raises(HTTPException) as exc:
        put_user_state("missing", UserStateRequest(saved=True), _request())

    assert exc.value.status_code == 404
    store.put.assert_not_called()

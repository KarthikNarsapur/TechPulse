from fastapi.testclient import TestClient

from app.api import app


client = TestClient(app)


class FakeSubscriptionStore:
    items: dict[tuple[str, str], dict] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    def list_for_user(self, user_id: str) -> list[dict]:
        return [item for (owner, _), item in self.items.items() if owner == user_id]

    def get(self, user_id: str, technology_id: str) -> dict | None:
        return self.items.get((user_id, technology_id))

    def put(self, item: dict) -> None:
        self.items[(item["user_id"], item["technology_id"])] = dict(item)

    def delete(self, user_id: str, technology_id: str) -> None:
        self.items.pop((user_id, technology_id), None)


def test_subscriptions_require_verified_jwt_claims() -> None:
    response = client.get("/api/v1/subscriptions")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "UNAUTHENTICATED"


def test_put_and_list_email_subscription(monkeypatch) -> None:
    FakeSubscriptionStore.items = {}
    monkeypatch.setattr("app.api._principal", lambda request: ("cognito-sub-123", "dev@example.com"))
    monkeypatch.setattr("app.api.SubscriptionStore", FakeSubscriptionStore)

    response = client.put("/api/v1/subscriptions/terraform", json={"channel": "email"})

    assert response.status_code == 200
    assert response.json()["item"]["technology_id"] == "terraform"
    assert response.json()["item"]["channel"] == "email"
    assert "secret_id" not in response.json()["item"]

    listed = client.get("/api/v1/subscriptions")
    assert listed.status_code == 200
    assert listed.json()["items"] == [response.json()["item"]]


def test_chat_subscription_requires_environment_scoped_secret_reference(monkeypatch) -> None:
    FakeSubscriptionStore.items = {}
    monkeypatch.setenv("TECHPULSE_ENVIRONMENT", "dev")
    monkeypatch.setattr("app.api._principal", lambda request: ("cognito-sub-123", "dev@example.com"))
    monkeypatch.setattr("app.api.SubscriptionStore", FakeSubscriptionStore)

    invalid = client.put(
        "/api/v1/subscriptions/terraform",
        json={"channel": "slack", "secret_id": "techpulse-prod-notifications-slack"},
    )
    assert invalid.status_code == 422

    valid = client.put(
        "/api/v1/subscriptions/terraform",
        json={"channel": "slack", "secret_id": "techpulse-dev-notifications-slack"},
    )
    assert valid.status_code == 200
    assert valid.json()["item"]["channel"] == "slack"
    assert valid.json()["item"]["secret_configured"] is True
    assert "secret_id" not in valid.json()["item"]


def test_subscription_rejects_unknown_technology(monkeypatch) -> None:
    monkeypatch.setattr("app.api._principal", lambda request: ("cognito-sub-123", "dev@example.com"))
    monkeypatch.setattr("app.api.SubscriptionStore", FakeSubscriptionStore)

    response = client.put("/api/v1/subscriptions/not-a-real-tech", json={"channel": "email"})
    assert response.status_code == 404


def test_delete_subscription_is_user_scoped(monkeypatch) -> None:
    FakeSubscriptionStore.items = {
        ("cognito-sub-123", "terraform"): {
            "user_id": "cognito-sub-123",
            "technology_id": "terraform",
            "channel": "email",
            "email": "dev@example.com",
        },
        ("another-user", "terraform"): {
            "user_id": "another-user",
            "technology_id": "terraform",
            "channel": "email",
            "email": "other@example.com",
        },
    }
    monkeypatch.setattr("app.api._principal", lambda request: ("cognito-sub-123", "dev@example.com"))
    monkeypatch.setattr("app.api.SubscriptionStore", FakeSubscriptionStore)

    response = client.delete("/api/v1/subscriptions/terraform")

    assert response.status_code == 200
    assert ("cognito-sub-123", "terraform") not in FakeSubscriptionStore.items
    assert ("another-user", "terraform") in FakeSubscriptionStore.items

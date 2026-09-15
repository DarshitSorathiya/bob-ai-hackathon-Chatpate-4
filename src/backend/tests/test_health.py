"""Smoke tests — verify the application starts and the health endpoint works."""

from fastapi.testclient import TestClient


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_response_envelope(client: TestClient) -> None:
    """Health response must follow the standard API envelope."""
    response = client.get("/api/v1/health")
    body = response.json()

    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert "request_id" in body["meta"]
    assert "timestamp" in body["meta"]
    assert body["error"] is None


def test_health_sets_request_id_header(client: TestClient) -> None:
    """Response must include X-Request-ID header."""
    response = client.get("/api/v1/health")
    assert "x-request-id" in response.headers


def test_health_with_incoming_request_id(client: TestClient) -> None:
    """If X-Request-ID is provided, it must be echoed back."""
    custom_id = "test-request-id-abc123"
    response = client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.headers.get("x-request-id") == custom_id
    body = response.json()
    assert body["meta"]["request_id"] == custom_id


def test_unknown_route_returns_404(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404

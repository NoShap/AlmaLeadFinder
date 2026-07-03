"""End-to-end API tests against the running docker-compose stack.

Unlike the hermetic tests in tests/, these exercise the real services: Postgres,
MinIO object storage, and the deployed frontend's middleware. They are excluded
from the default `pytest` run (see addopts in pyproject.toml); with the stack up
(`docker compose up --build`), run them with:

    pytest -m e2e

Browser-level journeys (form UX, login flow, dashboard actions) live in
frontend/e2e and run with Playwright; these tests cover the API contract.
"""

import os
import uuid

import httpx
import pytest

API_URL = os.environ.get("E2E_API_URL", "http://localhost:8000")
FRONTEND_URL = os.environ.get("E2E_FRONTEND_URL", "http://localhost:3000")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "attorney@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "Password1234!")

RESUME_BYTES = b"%PDF-1.4 fake e2e resume"

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="session")
def api():
    with httpx.Client(base_url=API_URL, timeout=10) as client:
        try:
            client.get("/api/health").raise_for_status()
        except httpx.HTTPError:
            pytest.skip(f"stack not running at {API_URL} — start it with `docker compose up`")
        yield client


@pytest.fixture(scope="session")
def auth_headers(api):
    response = api.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def submit_lead(api: httpx.Client, email: str) -> httpx.Response:
    return api.post(
        "/api/leads",
        data={"first_name": "Test", "last_name": "Prospect", "email": email},
        files={"resume": ("resume.pdf", RESUME_BYTES, "application/pdf")},
    )


def test_health(api):
    assert api.get("/api/health").status_code == 200


def test_unauthenticated_list_is_rejected(api):
    assert api.get("/api/leads").status_code == 401


def test_login_rejects_bad_credentials(api):
    response = api.post(
        "/api/auth/login", json={"email": ADMIN_EMAIL, "password": "wrong"}
    )
    assert response.status_code == 401


def test_lead_lifecycle(api, auth_headers):
    email = f"e2e-{uuid.uuid4().hex}@example.com"

    created = submit_lead(api, email)
    assert created.status_code == 201, created.text
    lead = created.json()
    assert lead["state"] == "PENDING"

    assert submit_lead(api, email).status_code == 409  # idempotent per email

    listed = api.get("/api/leads", params={"limit": 200}, headers=auth_headers)
    assert listed.status_code == 200
    assert any(item["id"] == lead["id"] for item in listed.json()["items"])

    resume = api.get(f"/api/leads/{lead['id']}/resume", headers=auth_headers)
    assert resume.status_code == 200
    assert resume.content == RESUME_BYTES  # byte-for-byte through object storage

    patched = api.patch(
        f"/api/leads/{lead['id']}", json={"state": "REACHED_OUT"}, headers=auth_headers
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["state"] == "REACHED_OUT"
    assert patched.json()["reached_out_at"] is not None

    again = api.patch(
        f"/api/leads/{lead['id']}", json={"state": "REACHED_OUT"}, headers=auth_headers
    )
    assert again.status_code == 409

    # Clean up so e2e runs don't clutter the real leads list.
    deleted = api.delete(f"/api/leads/{lead['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert api.get(f"/api/leads/{lead['id']}", headers=auth_headers).status_code == 404


def test_frontend_serves_and_middleware_gates_admin(api, auth_headers):
    with httpx.Client(base_url=FRONTEND_URL, timeout=10) as web:
        try:
            assert web.get("/").status_code == 200
        except httpx.TransportError:
            pytest.skip(f"frontend not running at {FRONTEND_URL}")

        anonymous = web.get("/admin")
        assert anonymous.status_code == 307
        assert anonymous.headers["location"].endswith("/admin/login")

        token = auth_headers["Authorization"].removeprefix("Bearer ")
        web.cookies.set("alma_admin_token", token)
        authed = web.get("/admin")
        assert authed.status_code == 200

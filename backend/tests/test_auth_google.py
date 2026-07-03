import pytest

from app.api.routes import auth as auth_route
from app.core.config import settings
from app.core.security import create_access_token

ALLOWLISTED = "nhshpr@gmail.com"


@pytest.fixture()
def google_configured(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "google_client_id", "test-client-id.apps.googleusercontent.com")


def fake_verifier(claims: dict):
    def verify(credential, request, audience):
        if credential == "bad-token":
            raise ValueError("invalid token")
        return claims
    return verify


class TestGoogleLogin:
    def test_not_configured_returns_503(self, client):
        response = client.post("/api/auth/google", json={"credential": "anything"})
        assert response.status_code == 503

    def test_allowlisted_account_gets_working_token(
        self, client, google_configured, monkeypatch
    ):
        monkeypatch.setattr(
            auth_route.google_id_token,
            "verify_oauth2_token",
            fake_verifier({"email": ALLOWLISTED, "email_verified": True}),
        )
        response = client.post("/api/auth/google", json={"credential": "good-token"})
        assert response.status_code == 200
        token = response.json()["access_token"]
        listing = client.get("/api/leads", headers={"Authorization": f"Bearer {token}"})
        assert listing.status_code == 200

    def test_non_allowlisted_account_rejected(self, client, google_configured, monkeypatch):
        monkeypatch.setattr(
            auth_route.google_id_token,
            "verify_oauth2_token",
            fake_verifier({"email": "intruder@gmail.com", "email_verified": True}),
        )
        response = client.post("/api/auth/google", json={"credential": "good-token"})
        assert response.status_code == 403

    def test_unverified_email_rejected(self, client, google_configured, monkeypatch):
        monkeypatch.setattr(
            auth_route.google_id_token,
            "verify_oauth2_token",
            fake_verifier({"email": ALLOWLISTED, "email_verified": False}),
        )
        response = client.post("/api/auth/google", json={"credential": "good-token"})
        assert response.status_code == 401

    def test_invalid_google_credential_rejected(self, client, google_configured, monkeypatch):
        monkeypatch.setattr(
            auth_route.google_id_token,
            "verify_oauth2_token",
            fake_verifier({}),
        )
        response = client.post("/api/auth/google", json={"credential": "bad-token"})
        assert response.status_code == 401


class TestAllowlistEnforcement:
    def test_valid_token_for_delisted_account_is_403(self, client):
        # A signed, unexpired token whose subject is no longer (or never was)
        # allowlisted must be rejected at request time, not just at login.
        token = create_access_token(subject="former-employee@gmail.com")
        response = client.get("/api/leads", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 403

    def test_allowlisted_subject_token_accepted(self, client):
        token = create_access_token(subject=ALLOWLISTED)
        response = client.get("/api/leads", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

    def test_fallback_admin_subject_still_accepted(self, client):
        token = create_access_token(subject=settings.admin_email)
        response = client.get("/api/leads", headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 200

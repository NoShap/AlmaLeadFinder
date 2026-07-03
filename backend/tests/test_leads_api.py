from app.core.config import settings

from tests.conftest import lead_form_data


def create_lead(client, **overrides):
    payload = lead_form_data(**overrides)
    return client.post("/api/leads", data=payload["data"], files=payload["files"])


class TestCreateLead:
    def test_success_creates_pending_lead(self, client, email_recorder):
        response = create_lead(client)
        assert response.status_code == 201
        body = response.json()
        assert body["first_name"] == "Ada"
        assert body["last_name"] == "Lovelace"
        assert body["email"] == "ada@example.com"
        assert body["state"] == "PENDING"
        assert body["reached_out_at"] is None
        assert "resume_path" not in body  # storage key must not leak

    def test_sends_prospect_and_attorney_emails(self, client, email_recorder):
        create_lead(client)
        recipients = {m.to for m in email_recorder.sent}
        assert recipients == {"ada@example.com", settings.attorney_notification_email}

    def test_prospect_and_attorney_emails_have_distinct_content(self, client, email_recorder):
        create_lead(client)
        by_recipient = {m.to: m for m in email_recorder.sent}
        prospect_msg = by_recipient["ada@example.com"]
        attorney_msg = by_recipient[settings.attorney_notification_email]
        assert prospect_msg.subject == "We received your information — Alma"
        assert "Hi Ada," in prospect_msg.html
        assert attorney_msg.subject == "New lead: Ada Lovelace"
        assert "ada@example.com" in attorney_msg.html
        assert prospect_msg.html != attorney_msg.html

    def test_email_failure_does_not_fail_submission(self, client, email_recorder, auth_headers):
        email_recorder.fail = True
        response = create_lead(client)
        assert response.status_code == 201
        listing = client.get("/api/leads", headers=auth_headers).json()
        assert listing["total"] == 1

    def test_invalid_email_rejected(self, client, email_recorder):
        response = create_lead(client, email="not-an-email")
        assert response.status_code == 422
        assert email_recorder.sent == []

    def test_non_pdf_or_word_resume_rejected(self, client):
        response = create_lead(client, filename="resume.txt", content_type="text/plain")
        assert response.status_code == 422

    def test_oversize_resume_rejected(self, client, monkeypatch):
        monkeypatch.setattr(settings, "max_resume_bytes", 10)
        response = create_lead(client, content=b"x" * 11)
        assert response.status_code == 422

    def test_missing_fields_rejected(self, client):
        response = client.post("/api/leads", data={"first_name": "Ada"})
        assert response.status_code == 422

    def test_duplicate_email_rejected(self, client, email_recorder, auth_headers):
        assert create_lead(client).status_code == 201
        emails_after_first = len(email_recorder.sent)
        response = create_lead(client, first_name="Ada2")
        assert response.status_code == 409
        assert len(email_recorder.sent) == emails_after_first  # no emails for the dupe
        listing = client.get("/api/leads", headers=auth_headers).json()
        assert listing["total"] == 1

    def test_duplicate_email_case_insensitive(self, client):
        assert create_lead(client, email="ada@example.com").status_code == 201
        assert create_lead(client, email="Ada@EXAMPLE.com").status_code == 409

    def test_email_stored_lowercase(self, client):
        body = create_lead(client, email="Ada@Example.COM").json()
        assert body["email"] == "ada@example.com"


class TestAuth:
    def test_list_requires_auth(self, client):
        assert client.get("/api/leads").status_code == 401

    def test_bad_token_rejected(self, client):
        response = client.get("/api/leads", headers={"Authorization": "Bearer nonsense"})
        assert response.status_code == 401

    def test_bad_credentials_rejected(self, client):
        response = client.post(
            "/api/auth/login", json={"email": settings.admin_email, "password": "wrong"}
        )
        assert response.status_code == 401


class TestLeadListing:
    def test_lists_all_submitted_leads(self, client, auth_headers):
        create_lead(client)
        create_lead(client, first_name="Grace", email="grace@example.com")
        body = client.get("/api/leads", headers=auth_headers).json()
        assert body["total"] == 2
        assert {item["first_name"] for item in body["items"]} == {"Ada", "Grace"}

    def test_detail_returns_lead(self, client, auth_headers):
        lead_id = create_lead(client).json()["id"]
        response = client.get(f"/api/leads/{lead_id}", headers=auth_headers)
        assert response.status_code == 200
        assert response.json()["id"] == lead_id

    def test_detail_404_for_unknown_lead(self, client, auth_headers):
        response = client.get(
            "/api/leads/00000000-0000-0000-0000-000000000000", headers=auth_headers
        )
        assert response.status_code == 404


class TestStateMachine:
    def test_mark_reached_out(self, client, auth_headers):
        lead_id = create_lead(client).json()["id"]
        response = client.patch(
            f"/api/leads/{lead_id}", json={"state": "REACHED_OUT"}, headers=auth_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["state"] == "REACHED_OUT"
        assert body["reached_out_at"] is not None

    def test_remarking_reached_out_conflicts(self, client, auth_headers):
        lead_id = create_lead(client).json()["id"]
        client.patch(f"/api/leads/{lead_id}", json={"state": "REACHED_OUT"}, headers=auth_headers)
        response = client.patch(
            f"/api/leads/{lead_id}", json={"state": "REACHED_OUT"}, headers=auth_headers
        )
        assert response.status_code == 409

    def test_pending_to_pending_conflicts(self, client, auth_headers):
        lead_id = create_lead(client).json()["id"]
        response = client.patch(
            f"/api/leads/{lead_id}", json={"state": "PENDING"}, headers=auth_headers
        )
        assert response.status_code == 409

    def test_unknown_state_rejected(self, client, auth_headers):
        lead_id = create_lead(client).json()["id"]
        response = client.patch(
            f"/api/leads/{lead_id}", json={"state": "CLOSED"}, headers=auth_headers
        )
        assert response.status_code == 422

    def test_transition_requires_auth(self, client):
        lead_id = create_lead(client).json()["id"]
        response = client.patch(f"/api/leads/{lead_id}", json={"state": "REACHED_OUT"})
        assert response.status_code == 401


class TestLeadDeletion:
    def test_delete_removes_lead_and_resume(self, client, auth_headers):
        lead_id = create_lead(client).json()["id"]
        response = client.delete(f"/api/leads/{lead_id}", headers=auth_headers)
        assert response.status_code == 204
        assert client.get(f"/api/leads/{lead_id}", headers=auth_headers).status_code == 404
        assert (
            client.get(f"/api/leads/{lead_id}/resume", headers=auth_headers).status_code == 404
        )
        assert client.get("/api/leads", headers=auth_headers).json()["total"] == 0

    def test_delete_unknown_lead_404(self, client, auth_headers):
        response = client.delete(
            "/api/leads/00000000-0000-0000-0000-000000000000", headers=auth_headers
        )
        assert response.status_code == 404

    def test_delete_requires_auth(self, client):
        lead_id = create_lead(client).json()["id"]
        assert client.delete(f"/api/leads/{lead_id}").status_code == 401


class TestResumeDownload:
    def test_download_returns_original_file(self, client, auth_headers):
        content = b"%PDF-1.4 the actual resume bytes"
        lead_id = create_lead(client, content=content).json()["id"]
        response = client.get(f"/api/leads/{lead_id}/resume", headers=auth_headers)
        assert response.status_code == 200
        assert response.content == content
        assert "resume.pdf" in response.headers["content-disposition"]

    def test_download_requires_auth(self, client):
        lead_id = create_lead(client).json()["id"]
        assert client.get(f"/api/leads/{lead_id}/resume").status_code == 401

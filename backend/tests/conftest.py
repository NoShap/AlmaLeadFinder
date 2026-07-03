import io

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.services import notifications
from app.services.email import EmailMessage, EmailService


class RecordingEmailService(EmailService):
    """Captures messages instead of sending; can be told to fail to test decoupling."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []
        self.fail = False

    def send(self, message: EmailMessage) -> None:
        if self.fail:
            raise RuntimeError("simulated provider outage")
        self.sent.append(message)


@pytest.fixture()
def email_recorder(monkeypatch: pytest.MonkeyPatch) -> RecordingEmailService:
    recorder = RecordingEmailService()
    monkeypatch.setattr(notifications, "get_email_service", lambda: recorder)
    return recorder


@pytest.fixture()
def client(tmp_path, monkeypatch: pytest.MonkeyPatch, email_recorder: RecordingEmailService):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))

    app = create_app()

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def auth_headers(client: TestClient) -> dict[str, str]:
    response = client.post(
        "/api/auth/login",
        json={"email": settings.admin_email, "password": settings.admin_password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def lead_form_data(
    first_name: str = "Ada",
    last_name: str = "Lovelace",
    email: str = "ada@example.com",
    filename: str = "resume.pdf",
    content: bytes = b"%PDF-1.4 fake resume",
    content_type: str = "application/pdf",
):
    return {
        "data": {"first_name": first_name, "last_name": last_name, "email": email},
        "files": {"resume": (filename, io.BytesIO(content), content_type)},
    }

"""Email delivery, decoupled from business logic.

Callers build an EmailMessage and hand it to an EmailService. Which transport is used
(Resend vs. console logging) is decided by configuration alone, so the app runs fully
end-to-end without external credentials.
"""

import abc
import logging
from dataclasses import dataclass

import httpx

from app.core.config import Settings, settings

logger = logging.getLogger(__name__)

RESEND_API_URL = "https://api.resend.com/emails"


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    html: str


class EmailService(abc.ABC):
    @abc.abstractmethod
    def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailService(EmailService):
    """Fallback transport: renders the email to the log instead of sending it."""

    def send(self, message: EmailMessage) -> None:
        logger.info(
            "[console email] to=%s subject=%r\n%s", message.to, message.subject, message.html
        )


class ResendEmailService(EmailService):
    def __init__(self, api_key: str, sender: str) -> None:
        self._api_key = api_key
        self._sender = sender

    def send(self, message: EmailMessage) -> None:
        response = httpx.post(
            RESEND_API_URL,
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={
                "from": self._sender,
                "to": [message.to],
                "subject": message.subject,
                "html": message.html,
            },
            timeout=10.0,
        )
        response.raise_for_status()


def get_email_service(config: Settings | None = None) -> EmailService:
    config = config or settings
    if config.resend_api_key:
        return ResendEmailService(api_key=config.resend_api_key, sender=config.email_from)
    return ConsoleEmailService()

"""Dispatch of lead-submission emails, run as a background task after the DB commit.

Deliberately decoupled from lead persistence: this function receives plain values (not
ORM objects, whose session is closed by the time the task runs), and any delivery
failure is logged rather than raised — a mail-provider outage must never fail or roll
back a form submission.
"""

import logging

from app.core.config import settings
from app.services import email_templates
from app.services.email import EmailService, get_email_service

logger = logging.getLogger(__name__)


def send_lead_submission_emails(
    first_name: str,
    last_name: str,
    prospect_email: str,
    email_service: EmailService | None = None,
) -> None:
    service = email_service or get_email_service()

    messages = [
        email_templates.prospect_confirmation(first_name=first_name, to=prospect_email),
        email_templates.attorney_notification(
            first_name=first_name,
            last_name=last_name,
            email=prospect_email,
            to=settings.attorney_notification_email,
        ),
    ]
    for message in messages:
        try:
            service.send(message)
        except Exception:
            logger.exception("Failed to send email to %s", message.to)

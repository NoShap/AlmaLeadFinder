import html

from app.services.email import EmailMessage


def prospect_confirmation(first_name: str, to: str) -> EmailMessage:
    safe_name = html.escape(first_name)
    return EmailMessage(
        to=to,
        subject="We received your information — Alma",
        html=(
            f"<p>Hi {safe_name},</p>"
            "<p>Thanks for reaching out to Alma. We've received your information and "
            "resume, and one of our attorneys will review your background and be in "
            "touch shortly.</p>"
            "<p>— The Alma Team</p>"
        ),
    )


def attorney_notification(first_name: str, last_name: str, email: str, to: str) -> EmailMessage:
    safe_first = html.escape(first_name)
    safe_last = html.escape(last_name)
    safe_email = html.escape(email)
    # Deliberately no hyperlink: Gmail treats link-bearing notification emails as
    # phishing-like (a localhost dashboard link got the message silently dropped —
    # verified empirically), and attorneys know where the dashboard lives.
    return EmailMessage(
        to=to,
        subject=f"New lead: {safe_first} {safe_last}",
        html=(
            "<p>A new lead was submitted:</p>"
            "<ul>"
            f"<li><strong>Name:</strong> {safe_first} {safe_last}</li>"
            f"<li><strong>Email:</strong> {safe_email}</li>"
            "</ul>"
            "<p>Review the lead and resume in the admin dashboard.</p>"
        ),
    )

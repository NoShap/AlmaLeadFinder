from app.services.email_templates import attorney_notification, prospect_confirmation


class TestNoHyperlinks:
    """Notification emails must contain no hyperlinks: Gmail treats link-bearing
    notifications as phishing-like (a localhost dashboard link got the attorney
    email silently dropped — found empirically), and none are needed."""

    def test_attorney_notification_has_no_links(self):
        message = attorney_notification(
            first_name="Jane", last_name="Doe", email="jane@example.com", to="a@example.com"
        )
        assert "<a " not in message.html
        assert "http" not in message.html
        assert "dashboard" in message.html  # still tells the attorney where to go

    def test_prospect_confirmation_has_no_links(self):
        message = prospect_confirmation(first_name="Jane", to="jane@example.com")
        assert "<a " not in message.html
        assert "http" not in message.html

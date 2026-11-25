import os
import time
import uuid

import pytest
import requests
from flask import Flask

from app.features.email import mail
from app.features.email.services import EmailService


@pytest.mark.integration
def test_email_is_visible_in_mailpit():
    api_url = os.getenv("MAILPIT_API_URL")
    if not api_url:
        pytest.skip("Set MAILPIT_API_URL to run the Mailpit integration test.")

    app = Flask(__name__)
    app.config.update(
        MAIL_SERVER=os.getenv("MAIL_SERVER", "localhost"),
        MAIL_PORT=int(os.getenv("MAIL_PORT", "1025")),
        MAIL_USE_TLS=os.getenv("MAIL_USE_TLS", "false").lower() in {"1", "true", "yes"},
        MAIL_USERNAME=os.getenv("MAIL_USERNAME") or None,
        MAIL_PASSWORD=os.getenv("MAIL_PASSWORD") or None,
        MAIL_DEFAULT_SENDER=os.getenv("MAIL_DEFAULT_SENDER", "noreply@uvlhub.local"),
    )
    mail.init_app(app)

    api_url = api_url.rstrip("/")
    try:
        requests.get(f"{api_url}/api/v1/info", timeout=2).raise_for_status()
    except requests.RequestException as exc:
        pytest.skip(f"Mailpit is not available at {api_url}: {exc}")

    subject = f"UVLHub Mailpit test {uuid.uuid4()}"
    body = "This message should be visible in the local Mailpit inbox."
    recipient = "mailpit-test@example.com"
    with app.app_context():
        EmailService().send_email(recipient, subject, body)

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = requests.get(f"{api_url}/api/v1/messages", timeout=2)
        response.raise_for_status()
        messages = response.json().get("messages", [])
        found = next((message for message in messages if message.get("Subject") == subject), None)
        if found:
            raw = requests.get(f"{api_url}/api/v1/message/{found['ID']}/raw", timeout=2)
            raw.raise_for_status()
            assert recipient in raw.text
            assert body in raw.text
            return
        time.sleep(0.1)

    pytest.fail(f"Mailpit did not receive email with subject {subject!r}.")
